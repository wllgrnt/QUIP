! HJ XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
! HJ X
! HJ X   libAtoms+QUIP: atomistic simulation library
! HJ X
! HJ X   Portions of this code were written by
! HJ X     Albert Bartok-Partay, Silvia Cereda, Gabor Csanyi, James Kermode,
! HJ X     Ivan Solt, Wojciech Szlachta, Csilla Varnai, Steven Winfield.
! HJ X
! HJ X   Copyright 2006-2010.
! HJ X
! HJ X   These portions of the source code are released under the GNU General
! HJ X   Public License, version 2, http://www.gnu.org/copyleft/gpl.html
! HJ X
! HJ X   If you would like to license the source code under different terms,
! HJ X   please contact Gabor Csanyi, gabor@csanyi.net
! HJ X
! HJ X   Portions of this code were written by Noam Bernstein as part of
! HJ X   his employment for the U.S. Government, and are not subject
! HJ X   to copyright in the USA.
! HJ X
! HJ X
! HJ X   When using this software, please cite the following reference:
! HJ X
! HJ X   http://www.libatoms.org
! HJ X
! HJ X  Additional contributions by
! HJ X    Alessio Comisso, Chiara Gattinoni, and Gianpietro Moras
! HJ X
! HJ XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

program lotf_metapot

  use libAtoms_module
  use QUIP_Module

  implicit None

  type(Atoms) :: dia, at
  type(InOutput) :: xml
  type(Potential) :: pot1, pot2
  real(dp), allocatable :: f(:,:), f_hyb(:,:)
  integer, pointer :: hybrid(:)
  integer :: i, n_steps
  type(Table) :: embedlist
  type(MetaPotential) :: lotf, forcemix
  type(DynamicalSystem) :: ds

  call system_initialise(PRINT_NORMAL,seed=2)
  call initialise(xml, 'lotf_params.xml')
  call initialise(pot1, 'IP SW label="PRB_31_plus_H"', xml)
  call rewind(xml)
  call initialise(pot2, 'IP SW label="eps_2.3"', xml)
  
  call diamond(dia, 5.44_dp, (/14/))
  call supercell(at, dia, 2, 2, 2)
  call randomise(at%pos, 0.1_dp)

  n_steps = 10

  allocate(f(3,at%N),f_hyb(3,at%N))

  call set_cutoff(at, cutoff(pot1)+2.0_dp)
  call calc_connect(at)

  ! Mark QM region
  call add_property(at, 'hybrid', 0)
  if (.not. assign_pointer(at, 'hybrid', hybrid)) &
       call system_abort('Cannot assign hybrid pointer')

  call append(embedlist, (/1,0,0,0/))
  call bfs_grow(at, embedlist, 2, nneighb_only=.true.)

  hybrid(int_part(embedlist,1)) = 1

  call print('embed list')
  call print(embedlist)

  ! Set up metapotentials for LOTF and for force mixing with the same buffer size
  call initialise(lotf, 'ForceMixing method=lotf_adj_pot_svd fit_hops=3 buffer_hops=3 '//&
       'randomise_buffer=T qm_args_str={carve_cluster=T single_cluster=T cluster_calc_connect=T}', pot1, pot2, dia)
  call initialise(forcemix, 'ForceMixing method=force_mixing buffer_hops=3 '//&
       'qm_args_str={carve_cluster=T single_cluster=T cluster_calc_connect=T}', pot1, pot2)

  call initialise(ds, at)
  
  call print_title('LOTF Metapotential')
  call print(lotf)

  call print_title('Force Mixing Metapotential')
  call print(forcemix)

  ! Standard dynamics
  do i=1,n_steps

     ! Update QM region
     ! ...

     call calc(lotf, ds%atoms, f=f)
     call calc(forcemix, ds%atoms, f=f_hyb)
     call advance_verlet(ds, 1.0_dp, f)
     call ds_print_status(ds, 'D', instantaneous=.true.)
     call print('force err '//ds%t//' '//rms_diff(f_hyb, f)//' '//maxval(abs(f_hyb-f)))
     call print('')

     if (mod(i,10) == 0) call calc_connect(ds%atoms)
  end do
  
  deallocate(f, f_hyb)
  call finalise(xml)
  call finalise(pot1)
  call finalise(pot2)
  call finalise(at)
  call finalise(ds)
  call finalise(dia)
  call system_finalise
  
end program lotf_metapot
