#!/usr/bin/env python
# encoding: utf-8


# Created by Brian Cherinka on 2016-05-18 15:08:29
# Licensed under a 3-clause BSD license.

# Revision History:
#     Initial Version: 2016-05-18 15:08:29 by Brian Cherinka
#     Last Modified On: 2016-05-18 15:08:29 by Brian


from __future__ import print_function
from __future__ import division
import json
from flask import jsonify
from flask_classy import route
from marvin.tools.plate import Plate
from marvin.api.base import BaseView
from marvin.core.exceptions import MarvinError


def _getPlate(plateid, nocubes=None):
    ''' Get a Plate Marvin Object '''
    plate = None
    results = {}

    if not str(plateid).isdigit():
        results['error'] = 'Error: plateid is not a numeric value'
        return plate, results

    try:
        plate = Plate(plateid=plateid, nocubes=nocubes, mode='local')
    except Exception as e:
        results['error'] = 'Failed to retrieve Plate for id {0}: {1}'.format(plateid, str(e))
    else:
        results['status'] = 1

    return plate, results


class PlateView(BaseView):
    """Class describing API calls related to plates."""

    route_base = '/plate/'

    @route('/<plateid>/', methods=['GET', 'POST'], endpoint='getPlate')
    def get(self, plateid):
        """Retrieve basic info about a plate

        .. :quickref: Plate; Get a plate given a plateid

        :param plateid: The plateid you want
        :form release: the release of MaNGA
        :resjson int status: status of response. 1 if good, -1 if bad.
        :resjson string error: error message, null if None
        :resjson json inconfig: json of incoming configuration
        :resjson json utahconfig: json of outcoming configuration
        :resjson string traceback: traceback of an error, null if None
        :resjson json data: dictionary of returned data
        :json string plateid: the plateid
        :json dict header: the cube header as a dict
        :resheader Content-Type: application/json
        :statuscode 200: no error
        :statuscode 422: invalid input parameters

        **Example request**:

        .. sourcecode:: http

           GET /marvin2/api/plate/8485/ HTTP/1.1
           Host: api.sdss.org
           Accept: application/json, */*

        **Example response**:

        .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json
           {
              "status": 1,
              "error": null,
              "inconfig": {"release": "MPL-5"},
              "utahconfig": {"release": "MPL-5", "mode": "local"},
              "traceback": null,
              "data": {"plateid": "8485",
                    "header": {"AIRMSMAX": "1.07643", "AIRMSMED": "1.04336", "AIRMSMIN": "1.03694", ... }
              }
           }

        """

        plate, results = _getPlate(plateid, nocubes=True)
        self.update_results(results)

        if not isinstance(plate, type(None)):
            # For now we don't return anything here, maybe later.

            platedict = {'plateid': plateid, 'header': plate._hdr}
            self.results['data'] = platedict

        return jsonify(self.results)

    @route('/<plateid>/cubes/', methods=['GET', 'POST'], endpoint='getPlateCubes')
    def getPlateCubes(self, plateid):
        """Returns a list of all the cubes for this plate

        .. :quickref: Plate; Get a list of all cubes for this plate

        :param plateid: The plateid you want
        :form release: the release of MaNGA
        :resjson int status: status of response. 1 if good, -1 if bad.
        :resjson string error: error message, null if None
        :resjson json inconfig: json of incoming configuration
        :resjson json utahconfig: json of outcoming configuration
        :resjson string traceback: traceback of an error, null if None
        :resjson json data: dictionary of returned data
        :json list plateifus: a list of plate-ifus for this plate
        :resheader Content-Type: application/json
        :statuscode 200: no error
        :statuscode 422: invalid input parameters

        **Example request**:

        .. sourcecode:: http

           GET /marvin2/api/plate/8485/cubes/ HTTP/1.1
           Host: api.sdss.org
           Accept: application/json, */*

        **Example response**:

        .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json
           {
              "status": 1,
              "error": null,
              "inconfig": {"release": "MPL-5"},
              "utahconfig": {"release": "MPL-5", "mode": "local"},
              "traceback": null,
              "data": {"plateifus": ["8485-12701","8485-12702","8485-1901","8485-1902", ...]
              }
           }

        """

        plate, results = _getPlate(plateid)
        self.update_results(results)

        if not isinstance(plate, type(None)):
            plateifus = [cube.plateifu for cube in plate]
            self.results['data'] = {'plateifus': plateifus}

        return jsonify(self.results)
