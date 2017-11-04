#!/usr/bin/env python
# encoding: utf-8
#
# spaxel.py
#
# Licensed under a 3-clause BSD license.
#
# Revision history:
#     11 Apr 2016 J. Sánchez-Gallego
#       Initial version


from __future__ import division
from __future__ import print_function

import itertools
import warnings

import numpy as np

import marvin
import marvin.core.core
import marvin.core.exceptions
import marvin.core.marvin_pickle
import marvin.utils.general.general

import marvin.tools.cube
import marvin.tools.maps
import marvin.tools.modelcube

from marvin.utils.general.structs import FuzzyDict

from marvin.core.exceptions import MarvinError, MarvinUserWarning, MarvinBreadCrumb

from marvin.utils.datamodel.dap import datamodel as dap_datamodel
from marvin.utils.datamodel.drp import datamodel as drp_datamodel


breadcrumb = MarvinBreadCrumb()


class DataModel(object):
    """A single ibject that holds the DRP and DAP datamodel."""

    def __init__(self, release):

        self.drp = drp_datamodel[release]
        self.dap = dap_datamodel[release]


class Spaxel(object):
    """A class that contains information about a spaxel..

    This class represents an spaxel with information from the reduced DRP
    spectrum, the DAP maps properties, and the model spectrum from the DAP
    logcube. A `.Spaxel` can be initialised with all or only part of that
    information, and either from a file, a database, or remotely via the
    Marvin API.

    Parameters:
        x,y (int):
            The `x` and `y` coordinates of the spaxel in the cube (0-indexed).
        cube_filename (str):
            The path of the data cube file containing the spaxel to load.
        maps_filename (str):
            The path of the DAP MAPS file containing the spaxel to load.
        modelcube_filename (str):
            The path of the DAP model cube file containing the spaxel to load.
        mangaid (str):
            The mangaid of the cube/maps of the spaxel to load.
        plateifu (str):
            The plate-ifu of the cube/maps of the spaxel to load (either
            ``mangaid`` or ``plateifu`` can be used, but not both).
        cube (`~marvin.tools.cube.Cube` object or bool):
            If ``cube`` is a `~marvin.tools.cube.Cube` object, that
            cube will be used for the `.Spaxel` instantiation. This mode
            is mostly intended for `~marvin.utils.general.general.getSpaxel`
            as it significantly improves loading time. Otherwise, ``cube`` can
            be ``True`` (default), in which case a cube will be instantiated
            using the input ``filename``, ``mangaid``, or ``plateifu``. If
            ``cube=False``, no cube will be used and the cube associated
            quantities will not be available..
        maps (`~marvin.tools.maps.Maps` object or bool)
            As ``cube`` but for the DAP measurements corresponding to the
            spaxel in the `.Maps` that matches ``template``. Since `.Spaxel`
            represents an unbinned quantity, the unbinned bintype will be
            used.
        modelcube (`marvin.tools.modelcube.ModelCube` object or bool)
            As ``maps`` but for the DAP measurements corresponding to the
            spaxel in the `.ModelCube`.
        template (str or None):
            The template use for kinematics. For MPL-4, one of
            ``'M11-STELIB-ZSOL', 'MILES-THIN', 'MIUSCAT-THIN'`` (if ``None``,
            defaults to ``'MIUSCAT-THIN'``). For MPL-5 and successive, the only
            option in ``'GAU-MILESHC'`` (``None`` defaults to it).
        release (str):
            The MPL/DR version of the data to use.
        lazy (bool):
            If ``False``, the spaxel data is loaded on instantiation.
            Otherwise, only the metadata is created. The associated quantities
            can be then loaded by calling `.Spaxel.load()`.
        kwargs (dict):
            Arguments to be passed to `.Cube`, `.Maps`, and `.ModelCube`
            when (and if) they are initialised.

    Attributes:
        cube_quantities (`~marvin.utils.general.structs.FuzzyDict`):
            A querable dictionary with the `.Spectrum` quantities
            derived from `.Cube` and matching ``x, y``.
        datamodel (object):
            An object contianing the DRP and DAP datamodels.
        maps_quantities (`~marvin.utils.general.structs.FuzzyDict`):
            A querable dictionary with the `.AnalysisProperty` quantities
            derived from `.Maps` and matching ``x, y``.
        model_quantities (`~marvin.utils.general.structs.FuzzyDict`):
            A querable dictionary with the `.Spectrum` quantities
            derived from `.ModelCube` and matching ``x, y``.
        ra,dec (float):
            Right ascension and declination of the spaxel. Not available until
            the spaxel has been `loaded <.Spaxel.load>`.

    """

    def __init__(self, x, y, cube_filename=None, maps_filename=None,
                 modelcube_filename=None, mangaid=None, plateifu=None,
                 cube=True, maps=True, modelcube=True, template=None,
                 template_kin=None, release=None, lazy=False, **kwargs):

        if template_kin is not None:
            warnings.warn('template_kin has been deprecated and will be removed '
                          'in a future version. Use template.',
                          marvin.core.exceptions.MarvinDeprecationWarning)
            template = template_kin

        self.cube = cube
        self.maps = maps
        self.modelcube = modelcube

        if not self.cube and not self.maps and not self.modelcube:
            raise MarvinError('either cube, maps, or modelcube must be True or '
                              'a Marvin Cube, Maps, or ModelCube object must be specified.')

        self.plateifu = self._check_versions('plateifu', plateifu)
        self.mangaid = self._check_versions('mangaid', mangaid)

        self._parent_shape = None

        # drop breadcrumb
        breadcrumb.drop(message='Initializing MarvinSpaxel {0}'.format(self.__class__),
                        category=self.__class__)

        # Checks versions
        input_release = release if release is not None else marvin.config.release
        self.release = self._check_versions('release', input_release, check_input=False)
        assert self.release in marvin.config._mpldict, 'invalid release version.'

        self.x = int(x)
        self.y = int(y)
        assert self.x is not None and self.y is not None, 'Spaxel requires x and y to initialise.'

        self.loaded = False
        self.datamodel = DataModel(self.release)

        self.bintype = self.datamodel.dap.get_bintype(self._check_versions('bintype', None))
        self.template = self.datamodel.dap.get_template(self._check_versions('template', template))

        self.cube_quantities = FuzzyDict({})
        self.maps_quantities = FuzzyDict({})
        self.model_quantities = FuzzyDict({})

        # Stores the remaining input values to be used with load()
        self.__input_params = dict(cube_filename=cube_filename,
                                   maps_filename=maps_filename,
                                   modelcube_filename=modelcube_filename,
                                   kwargs=kwargs)

        if lazy is False:
            self.load()

    def _check_versions(self, attr, input_value, check_input=True):
        """Checks that all input object have the same versions."""

        inputs = []
        for obj in [self.cube, self.maps, self.modelcube]:
            if obj is not None and not isinstance(obj, bool):
                inputs.append(obj)

        if len(inputs) == 1:
            if input_value is not None:
                if input_value is not None and check_input:
                    assert input_value == getattr(inputs[0], attr), \
                        'input {!r} does not match {!r}'.format(attr, inputs[0])
            return getattr(inputs[0], attr)

        output_value = input_value

        for obj_a, obj_b in itertools.combinations(inputs, 2):
            if hasattr(obj_a, attr) and hasattr(obj_b, attr):
                assert getattr(obj_a, attr) == getattr(obj_b, attr)
                if input_value is not None and check_input:
                    assert input_value == getattr(obj_a, attr), \
                        'input {!r} does not match {!r}'.format(attr, obj_a)
                output_value = getattr(obj_a, attr)

        return output_value

    def _set_radec(self):
        """Calculates ra and dec for this spaxel."""

        self.ra = None
        self.dec = None

        for obj in [self.cube, self.maps, self.modelcube]:
            if hasattr(obj, 'wcs'):
                if obj.wcs.naxis == 2:
                    self.ra, self.dec = obj.wcs.wcs_pix2world([[self.x, self.y]], 0)[0]
                elif obj.wcs.naxis == 3:
                    self.ra, self.dec, __ = obj.wcs.wcs_pix2world([[self.x, self.y, 0]], 0)[0]

    def load(self):
        """Loads the spaxel data."""

        if self.loaded:
            warnings.warn('already loaded', MarvinUserWarning)
            return

        self._load_cube()
        self._load_maps()
        # self._check_modelcube()

        self.loaded = True

    def save(self, path, overwrite=False):
        """Pickles the spaxel to a file.

        Parameters:
            path (str):
                The path of the file to which the `.Spaxel` will be saved.
                Unlike for other Marvin Tools that derive from
                `~marvin.core.core.MarvinToolsClass`, ``path`` is
                mandatory for `.Spaxel.save` as there is no default path for a
                given spaxel.
            overwrite (bool):
                If True, and the ``path`` already exists, overwrites it.
                Otherwise it will fail.

        Returns:
            path (str):
                The realpath to which the file has been saved.

        """

        return marvin.core.marvin_pickle.save(self, path=path, overwrite=overwrite)

    @classmethod
    def restore(cls, path, delete=False):
        """Restores a Spaxel object from a pickled file.

        If ``delete=True``, the pickled file will be removed after it has been
        unplickled. Note that, for objects with ``data_origin='file'``, the
        original file must exists and be in the same path as when the object
        was first created.

        """

        return marvin.core.marvin_pickle.restore(path, delete=delete)

    def _load_cube(self):
        """Loads the cube and the associated quantities."""

        # Checks that the cube is correct or load ones if cube == True.
        if not isinstance(self.cube, bool):
            assert isinstance(self.cube, marvin.tools.cube.Cube), \
                'cube is not an instance of marvin.tools.cube.Cube or a boolean.'
        elif self.cube is True:
            self.cube = marvin.tools.cube.Cube(filename=self.__input_params['cube_filename'],
                                               plateifu=self.plateifu,
                                               mangaid=self.mangaid,
                                               release=self.release)
        else:
            self.cube = None
            return

        if self.plateifu is not None:
            assert self.plateifu == self.cube.plateifu, \
                'input plateifu does not match the cube plateifu. '
        else:
            self.plateifu = self.cube.plateifu

        if self.mangaid is not None:
            assert self.mangaid == self.cube.mangaid, \
                'input mangaid does not match the cube mangaid. '
        else:
            self.mangaid = self.cube.mangaid

        self._parent_shape = self.cube._shape

        self.cube_quantities = self.cube._get_spaxel_quantities(self.x, self.y)

    def _load_maps(self):
        """Loads the cube and the properties."""

        if not isinstance(self.maps, bool):
            assert isinstance(self.maps, marvin.tools.maps.Maps), \
                'maps is not an instance of marvin.tools.maps.Maps or a boolean.'
        elif self.maps is True:
            self.maps = marvin.tools.maps.Maps(filename=self.__input_params['cube_filename'],
                                               mangaid=self.mangaid,
                                               plateifu=self.plateifu,
                                               bintype=self.__input_params['bintype'],
                                               template=self.__input_params['template'],
                                               release=self.release)
        else:
            self.maps = None
            return

        # Checks the bintype. The maps should always be unbinned unless this is
        # an instance of Bin.
        if self.maps.is_binned() and isinstance(self, Spaxel):
            raise MarvinError('cannot instantiate a Spaxel from a binned Maps.')

        if self.plateifu is not None:
            assert self.plateifu == self.maps.plateifu, \
                'input plateifu does not match the maps plateifu. '
        else:
            self.plateifu = self.maps.plateifu

        if self.mangaid is not None:
            assert self.mangaid == self.maps.mangaid, \
                'input mangaid does not match the maps mangaid. '
        else:
            self.mangaid = self.maps.mangaid

        self._parent_shape = self.maps._shape

        self.template = self.maps.template

        self.maps_quantities = self.maps._get_spaxel_quantities(self.x, self.y)

    # def _check_modelcube(self):
    #     """Loads the modelcube and associated arrays."""
    #
    #     if not isinstance(self.modelcube, bool):
    #         assert isinstance(self.modelcube, marvin.tools.modelcube.ModelCube), \
    #             'modelcube is not an instance of marvin.tools.modelcube.ModelCube or a boolean.'
    #     elif self.modelcube is True:
    #
    #         if self._is_MPL4():
    #             warnings.warn('ModelCube cannot be instantiated for MPL-4.',
    #                           MarvinUserWarning)
    #             self.modelcube = None
    #             return
    #
    #         self.modelcube = marvin.tools.modelcube.ModelCube(filename=self.__modelcube_filename,
    #                                                           mangaid=self.mangaid,
    #                                                           plateifu=self.plateifu,
    #                                                           template=self.template,
    #                                                           release=self._release)
    #     else:
    #         self.modelcube = None
    #         return
    #
    #     # Checks the bintype
    #     if self.modelcube.is_binned() and self.__allow_binned is False:
    #         raise MarvinError('cannot instantiate a Spaxel from a binned ModelCube.')
    #
    #     self.bintype = self.modelcube.bintype
    #     self.template = self.modelcube.template
    #
    #     if self.plateifu is not None:
    #         assert self.plateifu == self.modelcube.plateifu, \
    #             'input plateifu does not match the modelcube plateifu. '
    #     else:
    #         self.plateifu = self.modelcube.plateifu
    #
    #     if self.mangaid is not None:
    #         assert self.mangaid == self.modelcube.mangaid, \
    #             'input mangaid does not match the modelcube mangaid. '
    #     else:
    #         self.mangaid = self.modelcube.mangaid
    #
    #     self._parent_shape = self.modelcube.shape
    #
    #     self._load_models()

    def __repr__(self):
        """Spaxel representation."""

        if not self.loaded:
            return '<Marvin Spaxel (x={0.x:d}, y={0.y:d}, loaded=False)'.format(self)

        # Gets the coordinates relative to the centre of the cube/maps.
        y_mid, x_mid = np.array(self._parent_shape) / 2.
        x_centre = int(self.x - x_mid)
        y_centre = int(self.y - y_mid)

        return ('<Marvin Spaxel (plateifu={0.plateifu}, x={0.x:d}, y={0.y:d}; '
                'x_cen={1:d}, y_cen={2:d})>'.format(self, x_centre, y_centre))

    # def _load_models(self):
    #
    #     assert self.modelcube, 'a ModelCube is needed to initialise models.'
    #
    #     if self.modelcube.data_origin == 'file':
    #
    #         hdus = self.modelcube.data
    #         flux_array = hdus['FLUX'].data[:, self.y, self.x]
    #         flux_ivar = hdus['IVAR'].data[:, self.y, self.x]
    #         mask = hdus['MASK'].data[:, self.y, self.x]
    #         model_array = hdus['MODEL'].data[:, self.y, self.x]
    #         model_emline = hdus['EMLINE'].data[:, self.y, self.x]
    #         model_emline_base = hdus['EMLINE_BASE'].data[:, self.y, self.x]
    #         model_emline_mask = hdus['EMLINE_MASK'].data[:, self.y, self.x]
    #
    #     elif self.modelcube.data_origin == 'db':
    #
    #         if marvin.marvindb is None:
    #             raise MarvinError('there is not a valid DB connection.')
    #
    #         session = marvin.marvindb.session
    #         dapdb = marvin.marvindb.dapdb
    #
    #         modelcube_db_spaxel = session.query(dapdb.ModelSpaxel).filter(
    #             dapdb.ModelSpaxel.modelcube == self.modelcube.data,
    #             dapdb.ModelSpaxel.x == self.x, dapdb.ModelSpaxel.y == self.y).one()
    #
    #         if modelcube_db_spaxel is None:
    #             raise MarvinError('cannot find a modelcube spaxel for '
    #                               'x={0.x}, y={0.y}'.format(self))
    #
    #         flux_array = modelcube_db_spaxel.flux
    #         flux_ivar = modelcube_db_spaxel.ivar
    #         mask = modelcube_db_spaxel.mask
    #         model_array = modelcube_db_spaxel.model
    #         model_emline = modelcube_db_spaxel.emline
    #         model_emline_base = modelcube_db_spaxel.emline_base
    #         model_emline_mask = modelcube_db_spaxel.emline_mask
    #
    #     elif self.modelcube.data_origin == 'api':
    #
    #         # Calls /modelcubes/<name>/models/<path:path> to retrieve a
    #         # dictionary with all the models for this spaxel.
    #         url = marvin.config.urlmap['api']['getModels']['url']
    #         url_full = url.format(name=self.plateifu,
    #                               bintype=self.bintype.name,
    #                               template=self.template.name,
    #                               x=self.x, y=self.y)
    #
    #         try:
    #             response = api.Interaction(url_full, params={'release': self._release})
    #         except Exception as ee:
    #             raise MarvinError('found a problem when checking if remote model cube '
    #                               'exists: {0}'.format(str(ee)))
    #
    #         data = response.getData()
    #
    #         flux_array = np.array(data['flux_array'])
    #         flux_ivar = np.array(data['flux_ivar'])
    #         mask = np.array(data['flux_mask'])
    #         model_array = np.array(data['model_array'])
    #         model_emline = np.array(data['model_emline'])
    #         model_emline_base = np.array(data['model_emline_base'])
    #         model_emline_mask = np.array(data['model_emline_mask'])
    #
    #     # Instantiates the model attributes.
    #
    #     self.redcorr = Spectrum(self.modelcube.redcorr,
    #                             wavelength=self.modelcube.wavelength,
    #                             wavelength_unit=u.Angstrom)
    #
    #     self.model_flux = Spectrum(flux_array,
    #                                unit=u.erg / u.s / (u.cm ** 2) / spaxel_unit,
    #                                scale=1e-17,
    #                                wavelength=self.modelcube.wavelength,
    #                                wavelength_unit=u.Angstrom,
    #                                ivar=flux_ivar,
    #                                mask=mask)
    #
    #     self.model = Spectrum(model_array,
    #                           unit=u.erg / u.s / (u.cm ** 2) / spaxel_unit,
    #                           scale=1e-17,
    #                           wavelength=self.modelcube.wavelength,
    #                           wavelength_unit=u.Angstrom,
    #                           mask=mask)
    #
    #     self.emline = Spectrum(model_emline,
    #                            unit=u.erg / u.s / (u.cm ** 2) / spaxel_unit,
    #                            scale=1e-17,
    #                            wavelength=self.modelcube.wavelength,
    #                            wavelength_unit=u.Angstrom,
    #                            mask=model_emline_mask)
    #
    #     self.emline_base = Spectrum(model_emline_base,
    #                                 unit=u.erg / u.s / (u.cm ** 2) / spaxel_unit,
    #                                 scale=1e-17,
    #                                 wavelength=self.modelcube.wavelength,
    #                                 wavelength_unit=u.Angstrom,
    #                                 mask=model_emline_mask)
    #
    #     self.stellar_continuum = Spectrum(
    #         self.model.value - self.emline.value - self.emline_base.value,
    #         unit=u.erg / u.s / (u.cm ** 2) / spaxel_unit,
    #         scale=1e-17,
    #         wavelength=self.modelcube.wavelength,
    #         wavelength_unit=u.Angstrom,
    #         mask=model_emline_mask)
