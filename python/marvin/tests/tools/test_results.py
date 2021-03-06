# !usr/bin/env python2
# -*- coding: utf-8 -*-
#
# Licensed under a 3-clause BSD license.
#
# @Author: Brian Cherinka
# @Date:   2017-06-12 18:18:54
# @Last modified by:   Brian Cherinka
# @Last modified time: 2017-07-31 12:07:88

from __future__ import print_function, division, absolute_import
from marvin.tools.query import Query
from marvin.tools.results import Results, ResultSet, marvintuple
from marvin.tools.cube import Cube
from marvin.tools.maps import Maps
from marvin.tools.spaxel import Spaxel
from marvin.tools.modelcube import ModelCube
from marvin.utils.datamodel.query.base import ParameterGroup, query_params
from marvin import config
from marvin.core.exceptions import MarvinError
from collections import OrderedDict, namedtuple
import pytest
import copy
import six
import pandas as pd
import json


myplateifu = '8485-1901'
cols = ['cube.mangaid', 'cube.plate', 'cube.plateifu', 'ifu.name', 'nsa.z']
remotecols = [u'mangaid', u'plate', u'plateifu', u'ifu_name', u'z']


@pytest.fixture()
def limits(results):
    data = results.expdata['queries'][results.searchfilter]
    count = 10 if data['count'] >= 10 else data['count']
    return (10, count)


@pytest.fixture()
def results(query, request):
    searchfilter = request.param if hasattr(request, 'param') else 'nsa.z < 0.1 and cube.plate==8485'
    q = Query(searchfilter=searchfilter, mode=query.mode, limit=10, release=query._release)
    r = q.run()
    r.expdata = query.expdata
    yield r
    r = None


@pytest.fixture()
def columns(results):
    ''' returns the local or remote column syntax '''
    return ParameterGroup('Columns', cols)


class TestResultsColumns(object):

    def test_check_cols(self, results, columns):
        assert results.columns.full == columns.full
        assert results.columns.remote == columns.remote

    @pytest.mark.parametrize('col, errmsg', [('plate', 'plate is too ambiguous.  Did you mean one of')])
    def test_fail(self, results, col, errmsg):
        with pytest.raises(KeyError) as cm:
            col in results.columns
        assert cm.type == KeyError
        assert errmsg in str(cm.value)

    @pytest.mark.parametrize('results', [('nsa.z < 0.1 and haflux > 25')], indirect=True)
    @pytest.mark.parametrize('colmns, pars', [(['spaxelprop.x', 'spaxelprop.y', 'emline_gflux_ha_6564', 'bintype.name', 'template.name'],
                                               ['x', 'y', 'emline_gflux_ha_6564', 'bintype_name', 'template_name'])])
    def test_check_withadded(self, results, colmns, pars, columns):
        newcols = cols + colmns
        assert set(results._params) == set(newcols)

        newcols = copy.copy(columns)
        newcols.extend(ParameterGroup('Columns', colmns))
        assert set(results.columns.full) == set(newcols.full)
        assert set(results.columns.remote) == set(newcols.remote)

    @pytest.mark.parametrize('results', [('nsa.z < 0.1 and haflux > 25')], indirect=True)
    @pytest.mark.parametrize('full, name', [('nsa.z', 'z'), ('cube.plateifu', 'plateifu'),
                                            ('cube.mangaid', 'mangaid'),
                                            ('spaxelprop.emline_gflux_ha_6564', 'haflux')])
    def test_colnames(self, results, full, name):
        cols = results.columns
        assert full in cols
        assert name in cols
        col = cols[name]
        assert col.full == full


class TestMarvinTuple(object):

    def test_create(self, results):
        data = results.results[0].__dict__
        mt = marvintuple('ResultRow', data.keys())
        assert mt is not None
        assert hasattr(mt, 'mangaid')
        assert hasattr(mt, 'plateifu')

        row = mt(**data)
        assert row.plate == data['plate']
        assert row.mangaid == data['mangaid']
        assert row.plateifu == data['plateifu']

    def test_add(self, results):
        data = results.results[0].__dict__
        mt = marvintuple('ResultRow', 'mangaid, plate, plateifu, ifu_name')
        mt1 = marvintuple('ResultRow', 'z')

        row = mt(**{k: v for k, v in data.items() if k in ['mangaid', 'plate', 'plateifu', 'ifu_name']})
        row1 = mt1(**{k: v for k, v in data.items()})
        new_row = row + row1
        assert new_row is not None
        cols = ['mangaid', 'plate', 'plateifu', 'z']
        assert set(cols).issubset(set(new_row.__dict__.keys()))
        assert row.__dict__ <= new_row.__dict__


class TestResultSet(object):

    def test_list(self, results):
        reslist = results.results.to_list()
        assert isinstance(reslist, list)

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_sort(self, results):
        redshift = results.expdata['queries']['nsa.z < 0.1']['sorted']['1'][-1]
        results.getAll()
        results.results.sort('z')
        assert results.results['z'][0] == redshift

    def test_add(self, results):
        res = results.results
        res1 = res
        newres = res + res1
        newres1 = res1 + res
        assert res.columns.full == newres.columns.full
        assert newres == newres1


class TestResultsMisc(object):

    def test_showQuery(self, results):
        x = results.showQuery()
        assert isinstance(x, six.string_types)


class TestResultsOutput(object):

    def test_tofits(self, results, temp_scratch):
        file = temp_scratch.join('test_results.fits')
        results.toFits(filename=str(file), overwrite=True)
        assert file.check(file=1, exists=1) is True

    def test_tocsv(self, results, temp_scratch):
        file = temp_scratch.join('test_results.csv')
        results.toCSV(filename=str(file), overwrite=True)
        assert file.check(file=1, exists=1) is True

    def test_topandas(self, results):
        df = results.toDF()
        assert isinstance(df, pd.core.frame.DataFrame)

    def test_tojson(self, results):
        res = results.toJson()
        assert isinstance(res, six.string_types)
        json_res = json.loads(res)
        assert isinstance(json_res, list)


class TestResultsGetParams(object):

    def test_get_attribute(self, results, columns):
        res = results.results[0]
        assert isinstance(results.results, ResultSet) is True
        for i, name in enumerate(columns):
            assert res[i] == res.__getattribute__(name.remote)

    @pytest.mark.parametrize('col',
                             [(c) for c in cols],
                             ids=['cube.mangaid', 'cube.plate', 'cube.plateifu', 'ifu.name', 'nsa.z'])
    def test_get_list(self, results, col):
        assert col in results.columns
        obj = results.getListOf(col)
        assert obj is not None
        assert isinstance(obj, list) is True
        json_obj = results.getListOf(col, to_json=True)
        assert isinstance(json_obj, six.string_types)

    @pytest.mark.parametrize('results',
                             [('nsa.z < 0.1 and haflux > 25'),
                              ('nsa.z < 0.1'),
                              ('haflux > 25')], indirect=True)
    def test_get_list_all(self, results):
        q = Query(searchfilter=results.searchfilter, mode=results.mode, limit=1,
                  release=results._release, returnparams=results.returnparams)
        r = q.run(start=0, end=1)
        assert r.count == 1
        mangaids = r.getListOf('mangaid', return_all=True)
        assert len(mangaids) == r.totalcount
        assert len(mangaids) == results.expdata['queries'][results.searchfilter]['count']

    @pytest.mark.parametrize('ftype', [('dictlist'), ('listdict')])
    @pytest.mark.parametrize('name', [(None), ('mangaid'), ('z')], ids=['noname', 'mangaid', 'z'])
    def test_get_dict(self, results, ftype, name):
        output = results.getDictOf(name, format_type=ftype)

        if ftype == 'listdict':
            assert isinstance(output, list) is True
            assert isinstance(output[0], dict) is True
            if name is not None:
                assert set([name]) == set(list(output[0]))
            else:
                assert set(remotecols) == set(output[0])
        elif ftype == 'dictlist':
            assert isinstance(output, dict) is True
            assert isinstance(list(output.values())[0], list) is True
            if name is not None:
                assert set([name]) == set(list(output.keys()))
            else:
                assert set(remotecols) == set(output)

        json_obj = results.getDictOf(name, format_type=ftype, to_json=True)
        assert isinstance(json_obj, six.string_types)

    def test_get_dict_all(self, results):
        output = results.getDictOf('mangaid', return_all=True)
        assert len(output) == results.totalcount


class TestResultsSort(object):

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_sort(self, results, limits):
        results.sort('z')
        limit, count = limits
        data = results.expdata['queries'][results.searchfilter]['sorted']
        assert tuple(data['1']) == results.results[0]
        assert tuple(data[str(count)]) == results.results[count - 1]


class TestResultsPaging(object):

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_check_counts(self, results, limits):
        if results.mode == 'local':
            pytest.skip('skipping now due to weird issue with local results not same as remote results')
        results.sort('z')
        limit, count = limits
        data = results.expdata['queries'][results.searchfilter]
        assert results.totalcount == data['count']
        assert results.count == count
        assert len(results.results) == count
        assert results.limit == limit
        assert results.chunk == limit

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    @pytest.mark.parametrize('chunk, rows',
                             [(10, None),
                              (20, (10, 21))],
                             ids=['defaultchunk', 'chunk20'])
    def test_get_next(self, results, chunk, rows, limits):
        if results.mode == 'local':
            pytest.skip('skipping now due to weird issue with local results not same as remote results')
        limit, count = limits
        results.sort('z')
        results.getNext(chunk=chunk)
        data = results.expdata['queries'][results.searchfilter]['sorted']
        if results.count == results.totalcount:
            assert results.results[0] == tuple(data['1'])
            assert len(results.results) == count
        else:
            assert results.results[0] == tuple(data['11'])
            assert len(results.results) == chunk
            if rows:
                assert results.results[rows[0]] == tuple(data[str(rows[1])])

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    @pytest.mark.parametrize('index, chunk, rows',
                             [(30, 10, [(0, 21)]),
                              (45, 20, [(5, 31), (10, 36), (15, 41)])],
                             ids=['defaultchunk', 'chunk20'])
    def test_get_prev(self, results, index, chunk, rows, limits):
        if results.mode == 'local':
            pytest.skip('skipping now due to weird issue with local results not same as remote results')
        limit, count = limits
        results.sort('z')
        results.getSubset(index, limit=chunk)
        results.getPrevious(chunk=chunk)
        data = results.expdata['queries'][results.searchfilter]['sorted']
        if results.count == results.totalcount:
            assert results.results[0] == tuple(data['1'])
            assert len(results.results) == count
        elif results.count == 0:
            assert len(results.results) == 0
        else:
            assert len(results.results) == chunk
            if rows:
                for row in rows:
                    assert results.results[row[0]] == tuple(data[str(row[1])])

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    @pytest.mark.parametrize('index, chunk, rows',
                             [(35, 10, [(0, 36)]),
                              (30, 20, [(0, 31), (15, 46)])],
                             ids=['defaultchunk', 'chunk20'])
    def test_get_set(self, results, index, chunk, rows, limits):
        if results.mode == 'local':
            pytest.skip('skipping now due to weird issue with local results not same as remote results')
        limit, count = limits
        results.sort('z')
        results.getSubset(index, limit=chunk)
        data = results.expdata['queries'][results.searchfilter]['sorted']
        if results.count == results.totalcount:
            assert results.results[0] == tuple(data['1'])
            assert len(results.results) == count
        elif results.count == 0:
            assert len(results.results) == 0
        else:
            assert len(results.results) == chunk
            if rows:
                for row in rows:
                    assert results.results[row[0]] == tuple(data[str(row[1])])

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_extend_set(self, results):
        res = results.getSubset(0, limit=1)
        assert results.count == 1
        assert len(results.results) == 1
        results.extendSet(start=1, chunk=2)
        setcount = 3 if results.count > 3 else results.count
        assert results.count == setcount
        assert len(results.results) == setcount

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_loop(self, results):
        res = results.getSubset(0, limit=1)
        assert results.count == 1
        results.loop(chunk=500)
        assert results.count == results.expdata['queries'][results.searchfilter]['count']
        assert results.count == results.totalcount

    @pytest.mark.parametrize('results', [('nsa.z < 0.1')], indirect=True)
    def test_get_all(self, results):
        res = results.getAll()
        assert results.count == results.totalcount


class TestResultsPickling(object):

    def test_pickle_save(self, results, temp_scratch):
        file = temp_scratch.join('test_results.mpf')
        path = results.save(str(file), overwrite=True)
        assert file.check() is True

    def test_pickle_restore(self, results, temp_scratch):
        file = temp_scratch.join('test_results.mpf')
        path = results.save(str(file), overwrite=True)
        assert file.check() is True
        r = Results.restore(str(file))
        assert r.searchfilter == results.searchfilter


class TestResultsConvertTool(object):

    @pytest.mark.parametrize('results', [('nsa.z < 0.1 and haflux > 25')], indirect=True)
    @pytest.mark.parametrize('objtype, tool',
                             [('cube', Cube), ('maps', Maps), ('spaxel', Spaxel),
                              ('modelcube', ModelCube)])
    def test_convert_success(self, results, objtype, tool, exporigin):
        if config.release == 'MPL-4' and objtype == 'modelcube':
            pytest.skip('no modelcubes in mpl-4')

        results.convertToTool(objtype, limit=1)
        assert results.objects is not None
        assert isinstance(results.objects, list) is True
        assert isinstance(results.objects[0], tool) is True
        if objtype != 'spaxel':
            assert results.mode == results.objects[0].mode

    @pytest.mark.parametrize('objtype, error, errmsg',
                             [('modelcube', MarvinError, "ModelCube requires at least dapver='2.0.2'"),
                              ('spaxel', AssertionError, 'Parameters must include spaxelprop.x and y in order to convert to Marvin Spaxel')],
                             ids=['mcminrelease', 'nospaxinfo'])
    def test_convert_failures(self, results, objtype, error, errmsg):
        if config.release > 'MPL-4' and objtype == 'modelcube':
            pytest.skip('modelcubes in post mpl-4')

        with pytest.raises(error) as cm:
            results.convertToTool(objtype, limit=1)
        assert cm.type == error
        assert errmsg in str(cm.value)


