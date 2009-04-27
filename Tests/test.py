#!/usr/bin/env python

import os, sys, re, getopt, subprocess
from difflib import ndiff

def loadtests(testfiles):
   tests = []
   for testfile in testfiles:
      data = open(testfile).read()

      endl = data.index('\n---')
      command = data[:endl]
      data = data[endl+4:]
      
      fields = data.split('---')

      if len(fields) % 2 != 0:
         raise ValueError('Badly formed testfile %s' % testfile)

      infiles = {}
      outfiles = {}
      for name, contents in zip(fields[::2], fields[1::2]):
         if name[0] == '<':
            infiles[name[1:].strip()]  = contents[1:].splitlines(1)
         elif name[0] == '>':
            outfiles[name[1:].strip()] = contents[1:].splitlines(1)
      
      if not 'stdout' in outfiles:
         raise ValueError('Missing stdout section in testfile %s' % testfile)
      
      tests.append((testfile, command, infiles, outfiles))

   return tests


def remove_ignored_stdout_lines(line):
   return not (line.startswith('System::Hello World') or
               line.startswith('System::Finalise') or
	       line.startswith('TIMER'))


def runtest(command, diff_method, infiles, outfiles, capture_output=True):

   for name, contents in infiles.iteritems():
      if name != 'stdin':
         f = open(name,'w')
         f.writelines(contents)
         f.close()

   # Remove old output files
   for name, contents in outfiles.iteritems():
      if name != 'stdout':
         if os.path.exists(name): os.unlink(name)

   args = command.split()
   exe_name = args[0]
   exe = '%s/../build.%s/%s' % (os.environ['PWD'], ARCH, args[0])

   if not os.path.isfile(exe):
      print '%s does not exist, trying to build in QUIP_Programs' % exe
      if os.system('cd .. && make QUIP_Programs/%s' % exe_name) != 0:
         print 'Cannot compile %s' % exe_name
         return False

   args[0] = exe

   if capture_output:
      stdout = subprocess.PIPE
      stderr = subprocess.PIPE
   else:
      stdout = None
      stderr = None

   proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
                           
   input = None
   if 'stdin' in infiles:
      input = ''.join(infiles['stdin'])

   stdout, stderr = proc.communicate(input)

   if not capture_output:
      return False

   if stderr != '':
      print 'Error occurred running test.'
      print stderr
      return False
   
   cmpout = {}
   cmpout['stdout'] = (filter(remove_ignored_stdout_lines,[s+'\n' for s in stdout.split('\n')]),
                       filter(remove_ignored_stdout_lines,outfiles['stdout']))

   for name, contents in outfiles.iteritems():
      if name != 'stdout':
         if not os.path.exists(name):
            print 'Output file %s not produced' % name
            return False
         
         f = open(name,'r')
         exp_contents = f.readlines()
         cmpout[name] = (contents, exp_contents)

   diffs = {}
   reduced_diffs = {}
   for name, (contents, exp_contents) in cmpout.iteritems():
      diffs[name] = list(do_diff(contents, exp_contents, diff_method))
   
   no_differences = True
   for name,rd in diffs.iteritems():
      if rd != []:
         no_differences = False
         print 'Mismatch in file %s' % name
         print ''.join(rd)
         #print ''.join(cmpout[name][0])
         #print ''.join(cmpout[name][1])

   # remove tmp files
   for fname in infiles.keys()+outfiles.keys():
      if not fname in ('stdin','stdout'):
         if os.path.exists(fname): os.unlink(fname)

   return no_differences

# Use ndiff(1) if found, otherwise use built in diff
def do_diff(a, b, diff_method):
   if diff_method != 'built in':
      fnamea, fnameb = os.tmpnam(), os.tmpnam()
      fa, fb  = open(fnamea, 'w'), open(fnameb, 'w')
      fa.writelines(a)
      fb.writelines(b)
      fa.close()
      fb.close()
      cin, cout, cerr = os.popen3("%s -abserr 1e-10 -separators '[ \t=\(\)\n]' %s %s" % (diff_method, fnamea, fnameb))
      result = cout.readlines()
      result.extend(cerr.readlines())
      result = filter(lambda s: not s.startswith('###'), result)
      os.remove(fnamea)
      os.remove(fnameb)
      return result
   else:
      return ndiff(a, b)


def runtests(tests, capture_output):
   # Look for ndiff(1) executable somewhere on PATH
   diff_method = 'built in'
   for p in os.environ['PATH'].split(':'):
      candidate_path = os.path.join(p,'ndiff')
      if os.path.exists(candidate_path):
         diff_method = candidate_path
         break

   if diff_method != 'built in':
      # Disable RuntimeWarning printed by os.tmpnam
      def nowarning(message, category, filename, lineno, file=None, line=None): pass
      import warnings
      warnings.showwarning = nowarning

   print 'Running %d regression tests using diff method: %s' % (len(tests), diff_method)
   print
   n_fail = 0
   failed_tests = []
   for name, command, infiles, outfiles in tests:

      print '  Running test : %s  ' % name, 
      if runtest(command, diff_method, infiles, outfiles, capture_output):
         print '%s: OK' % name
      else:
         print '%s: FAIL' % name
         failed_tests.append(name)
         n_fail += 1

   print
   print 'Failed %d tests:  \n%s' % (n_fail, '\n  '.join(failed_tests))
   return n_fail == 0


def mktest(name, command, read_stdin=False, infiles=[], outfiles=[]):

   testfile = open(name, 'w')
   testfile.write(command+'\n')

   if infiles != []:
      for fname in infiles:
         testfile.write('---<%s---\n' % fname)
         lines = open(fname,'r').readlines()
         testfile.writelines(lines)

   print 'running command %s' % command

   # escape "s from shell
   command = command.replace('"',r'\"')

   stdin, stdout = os.popen2('./build.%s/%s' % (ARCH, command))

   if read_stdin:
      testfile.write('---<stdin---\n')
      inputlines = sys.stdin.readlines()
      testfile.writelines(inputlines)
      stdin.writelines(inputlines)
      stdin.close()

   testfile.write('--->stdout---\n')
   testfile.writelines(stdout.readlines())

   if outfiles != []:
      for fname in outfiles:
         testfile.write('--->%s---\n' % fname)
         lines = open(fname, 'r').readlines()
         testfile.writelines(lines)

   testfile.close()
         

def print_usage():
   """Regression testing program
   James Kermode <jrk33@cam.ac.uk>
   
   Usage:  
     To run tests:       QUIP_ARCH=arch %s -r [-d] TESTFILE...' % sys.argv[0
     To make a new test: QUIP_ARCH=arch -m TESTFILE [-i INFILE]...'  % sys.argv[0
                            [-o OUTFILE]... COMMAND
   
   where QUIP_ARCH is the architecture (can be set in an environment
   variable), TESTFILE is a file containing a test case, COMMAND is the
   test case command, and INFILE and OUTFILE are input and output
   files for the new test case. If "-i stdin" is present then stdin
   will be read and passed along to the test program. The -d option
   indicates debug mode.
   """
      
if __name__ == '__main__':

   if len(sys.argv) < 3:
      print_usage()
      sys.exit(1)

   if 'QUIP_ARCH' in os.environ:
      ARCH = os.environ['QUIP_ARCH']
   else:
      print 'QUIP_ARCH environment variable not set.'
      print_usage()
      sys.exit(1)

   opts, args = getopt.getopt(sys.argv[1:],'rm:i:o:d')

   if opts[0][0] == '-r':
      try:
         tests = loadtests(args)
      except ValueError,v:
         print 'Error loading testfile: %s' % v
         sys.exit(1)
      runtests(tests, capture_output=not ('-d','') in opts)
      
   elif opts[0][0] == '-m':

      testfile = opts[0][1]

      infiles = []
      outfiles = []

      for opt, value in opts:
         if opt == '-i': infiles.append(value)
         if opt == '-o': outfiles.append(value)

      command = ' '.join(args)

      print infiles, outfiles, command

      read_stdin = False
      if 'stdin' in infiles:
         read_stdin = True
         del infiles[infiles.index('stdin')]

      mktest(testfile, command, read_stdin, infiles, outfiles)
                         
      
   else:
      print_usage()
      sys.exit(1)
