import numpy as np
import numpy.testing as npt

import nibabel as nib
import dipy.io as dio
import dipy.data as dpd
import dipy.core.gradients as dpg
from dipy.sims.voxel import multi_tensor_dki, single_tensor


def assert_image_shape_affine(filename, shape, affine):
    npt.assert_(os.path.isfile(filename))
    image = nib.load(filename)
    npt.assert_equal(image.shape, shape)
    npt.assert_array_almost_equal(image.get_affine(), affine)


def make_dti_data(out_fbval, out_fbvec, out_fdata, out_shape=(5, 6, 7)):
    """
    Create a synthetic data-set with a single shell acquisition

    out_fbval, out_fbvec, out_fdata : str
        Full paths to generated data and bval/bvec files

    out_shape : tuple
        The 3D shape of the output volum

    """
    fimg, fbvals, fbvecs = dpd.get_data('small_64D')
    img = nib.load(fimg)
    bvals, bvecs = dio.read_bvals_bvecs(fbvals, fbvecs)
    gtab = dpg.gradient_table(bvals, bvecs)

    # Simulate a signal based on the DTI model:
    signal = single_tensor(gtab, S0=100)
    DWI = np.zeros(out_shape + (len(gtab.bvals), ))
    DWI[:] = signal
    nib.save(nib.Nifti1Image(DWI, img.affine), out_fdata)
    np.savetxt(out_fbval, bvals)
    np.savetxt(out_fbvec, bvecs)


def make_dki_data(out_fbval, out_fbvec, out_fdata, out_shape=(5, 6, 7)):
    """
    Create a synthetic data-set with a 2-shell acquisition

    out_fbval, out_fbvec, out_fdata : str
        Full paths to generated data and bval/bvec files

    out_shape : tuple
        The 3D shape of the output volum

    """
    # This is one-shell (b=1000) data:
    fimg, fbvals, fbvecs = dpd.get_data('small_64D')
    img = nib.load(fimg)
    bvals, bvecs = dio.read_bvals_bvecs(fbvals, fbvecs)
    # So  we create two shells out of it
    bvals_2s = np.concatenate((bvals, bvals * 2), axis=0)
    bvecs_2s = np.concatenate((bvecs, bvecs), axis=0)
    gtab_2s = dpg.gradient_table(bvals_2s, bvecs_2s)

    # Simulate a signal based on the DKI model:
    mevals_cross = np.array([[0.00099, 0, 0], [0.00226, 0.00087, 0.00087],
                             [0.00099, 0, 0], [0.00226, 0.00087, 0.00087]])
    angles_cross = [(80, 10), (80, 10), (20, 30), (20, 30)]
    fie = 0.49
    frac_cross = [fie * 50, (1 - fie) * 50, fie * 50, (1 - fie) * 50]
    # Noise free simulates
    signal_cross, dt_cross, kt_cross = multi_tensor_dki(gtab_2s, mevals_cross,
                                                        S0=100,
                                                        angles=angles_cross,
                                                        fractions=frac_cross,
                                                        snr=None)
    DWI = np.zeros(out_shape + (len(gtab_2s.bvals), ))
    DWI[:] = signal_cross
    nib.save(nib.Nifti1Image(DWI, img.affine), out_fdata)
    np.savetxt(out_fbval, bvals_2s)
    np.savetxt(out_fbvec, bvecs_2s)


"""
What follows is code from Dipy.

The code is (c) Dipy developers, 2009 -- 2016, and released under a BSD license

For details, see: https://github.com/nipy/dipy/blob/master/LICENSE

"""

"""

Module to help tests check script output

Provides class to be instantiated in tests that check scripts.  Usually works
something like this in a test module::

    from .scriptrunner import ScriptRunner
    runner = ScriptRunner()

Then, in the tests, something like::

    code, stdout, stderr = runner.run_command(['my-script', my_arg])
    assert_equal(code, 0)
    assert_equal(stdout, b'This script ran OK')
"""
import sys  # noqa
import os  # noqa
from os.path import (dirname, join as pjoin, isfile,  # noqa
                     isdir, realpath, pathsep)

from subprocess import Popen, PIPE  # noqa

try:  # Python 2
    string_types = basestring,
except NameError:  # Python 3
    string_types = str,


def _get_package():
    """ Workaround for missing ``__package__`` in Python 3.2
    """
    if(('__package__' in globals()) and (__package__ is not None)):
        return __package__
    return __name__.split('.', 1)[0]


# Same as __package__ for Python 2.6, 2.7 and >= 3.3
MY_PACKAGE = _get_package()


def local_script_dir(script_sdir):
    """ Get local script directory if running in development dir, else None
    """
    # Check for presence of scripts in development directory.  ``realpath``
    # allows for the situation where the development directory has been linked
    # into the path.
    package_path = dirname(__import__(MY_PACKAGE).__file__)
    above_us = realpath(pjoin(package_path, '..'))
    devel_script_dir = pjoin(above_us, script_sdir)
    if isfile(pjoin(above_us, 'setup.py')) and isdir(devel_script_dir):
        return devel_script_dir
    return None


def local_module_dir(module_name):
    """ Get local module directory if running in development dir, else None
    """
    mod = __import__(module_name)
    containing_path = dirname(dirname(realpath(mod.__file__)))
    if containing_path == realpath(os.getcwd()):
        return containing_path
    return None


class ScriptRunner(object):
    """ Class to run scripts and return output

    Finds local scripts and local modules if running in the development
    directory, otherwise finds system scripts and modules.
    """

    def __init__(self,
                 script_sdir='scripts',
                 module_sdir=MY_PACKAGE,
                 debug_print_var=None,
                 output_processor=lambda x: x):
        """ Init ScriptRunner instance

        Parameters
        ----------
        script_sdir : str, optional
            Name of subdirectory in top-level directory (directory containing
            setup.py), to find scripts in development tree.  Typically
            'scripts', but might be 'bin'.
        module_sdir : str, optional
            Name of subdirectory in top-level directory (directory containing
            setup.py), to find main package directory.
        debug_print_vsr : str, optional
            Name of environment variable that indicates whether to do debug
            printing or no.
        output_processor : callable
            Callable to run on the stdout, stderr outputs before returning
            them.  Use this to convert bytes to unicode, strip whitespace, etc.
        """
        self.local_script_dir = local_script_dir(script_sdir)
        self.local_module_dir = local_module_dir(module_sdir)
        if debug_print_var is None:
            debug_print_var = '{0}_DEBUG_PRINT'.format(module_sdir.upper())
        self.debug_print = os.environ.get(debug_print_var, False)
        self.output_processor = output_processor

    def run_command(self, cmd, check_code=True):
        """ Run command sequence `cmd` returning exit code, stdout, stderr

        Parameters
        ----------
        cmd : str or sequence
            string with command name or sequence of strings defining command
        check_code : {True, False}, optional
            If True, raise error for non-zero return code

        Returns
        -------
        returncode : int
            return code from execution of `cmd`
        stdout : bytes (python 3) or str (python 2)
            stdout from `cmd`
        stderr : bytes (python 3) or str (python 2)
            stderr from `cmd`
        """
        if isinstance(cmd, string_types):
            cmd = [cmd]
        else:
            cmd = list(cmd)
        if self.local_script_dir is not None:
            # Windows can't run script files without extensions
            # natively so we need to run local scripts (no extensions)
            # via the Python interpreter.  On Unix, we might have the
            # wrong incantation for the Python interpreter
            # in the hash bang first line in the source file. So, either way,
            # run the script through the Python interpreter
            cmd = [sys.executable,
                   pjoin(self.local_script_dir, cmd[0])] + cmd[1:]
        elif os.name == 'nt':
            # Need .bat file extension for windows
            cmd[0] += '.bat'
        if os.name == 'nt':
            # Quote any arguments with spaces. The quotes delimit the arguments
            # on Windows, and the arguments might be files paths with spaces.
            # On Unix the list elements are each separate arguments.
            cmd = ['"{0}"'.format(c) if ' ' in c else c for c in cmd]
        if self.debug_print:
            print("Running command '%s'" % cmd)
        env = os.environ
        if self.local_module_dir is not None:
            # module likely comes from the current working directory.
            # We might need that directory on the path if we're running
            # the scripts from a temporary directory
            env = env.copy()
            pypath = env.get('PYTHONPATH', None)
            if pypath is None:
                env['PYTHONPATH'] = self.local_module_dir
            else:
                env['PYTHONPATH'] = self.local_module_dir + pathsep + pypath
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env)
        stdout, stderr = proc.communicate()
        if proc.poll() is None:
            proc.terminate()
        if check_code and proc.returncode != 0:
            raise RuntimeError(
                """Command "{0}" failed with
                stdout
                ------
                {1}
                stderr
                ------
                {2}
                """.format(cmd, stdout, stderr))
        opp = self.output_processor
        return proc.returncode, opp(stdout), opp(stderr)


def make_tracking_data(out_fbval, out_fbvec, out_fdata):
    fimg, fbvals, fbvecs = dpd.get_data('small_101D')
    bvals = np.loadtxt(fbvals)
    bvecs = np.loadtxt(fbvecs)
    # We simulate an affine with no shear component:
    affine = np.array([[2., 0., 0., -80.],
                       [0., 2., 0., -120.],
                       [0., 0., 2., -60.],
                       [0., 0., 0., 1.]])

    nib.save(nib.Nifti1Image(nib.load(fimg).get_data(), affine), out_fdata)
    np.savetxt(out_fbval, bvals)
    np.savetxt(out_fbvec, bvecs)
