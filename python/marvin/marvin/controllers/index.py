#!/usr/bin/python

import os, glob, random

import flask
from flask import request, render_template, send_from_directory, current_app, session as current_session, jsonify
from manga_utils import generalUtils as gu
from collections import OrderedDict

from ..model.database import db
from ..utilities import setGlobalVersion

import sdss.internal.database.utah.mangadb.DataModelClasses as datadb

try:
    from . import valueFromRequest
except ValueError:
    pass
    
    
index_page = flask.Blueprint("index_page", __name__)

@index_page.route('/marvin/setversion', methods=['GET','POST'])
@index_page.route('/setversion', methods=['GET','POST'])
def setVersion():
    ''' Set version to use during MaNGA SAS '''
    
    version = valueFromRequest(key='version',request=request, default=None)
    activepage = valueFromRequest(key='activepage',request=request, default=None)
    current_session['currentver'] = version
    print(activepage)

    return jsonify(result='set the version')

@index_page.route('/', methods=['GET'])
@index_page.route('/index', methods=['GET'])
@index_page.route('/index.html', methods=['GET'])
@index_page.route('/marvin/index.html', methods=['GET'])
def index():
    ''' Documentation here. '''
    
    session = db.Session()    
    index = {}
    index['title'] = "Marvin"
    
    # set global version
    setGlobalVersion()
    version = current_session['currentver']
    
    current_app.logger.info('Loading index page...')
    
    # find and grab all images ; convert paths to sas paths
    current_app.logger.info('Building image list...')
    redux = os.path.join(os.getenv('MANGA_SPECTRO_REDUX'),version)
    sasredux = os.path.join(os.getenv('SAS_REDUX'),version)
    try: sasurl = os.getenv('SAS_URL')
    except: sasurl = None
    good = os.path.isdir(redux)
    index['good'] = good
    imagedir = os.path.join(redux,'*','stack','images')
    images = glob.glob(os.path.join(imagedir,'*.png'))

    if any(images):
        images = [os.path.join(sasurl,sasredux,i.rsplit('/',4)[1],'stack/images',i.split('/')[-1]) for i in images]
        
        # randomize the images
        current_app.logger.info('Selecting 100 random images...')
        if len(images) < 100: biglist = [random.choice(images) for i in xrange(100)]
        else: biglist = random.sample(images,100)
        images = biglist
        
        # make unique image dictionary
        current_app.logger.info('Building image dictionary...')
        imdict = OrderedDict()
        for image in biglist:
            plate = image.rsplit('/',4)[1]
            name = image.rsplit('/',4)[-1].split('.')[0]
            plateifu = '{0}-{1}'.format(plate,name)
            imdict[plateifu] = image
        index['imdict'] = imdict
    else: index['imdict'] = None
    
    # get all galaxy cubes from latest tag
    current_app.logger.info('Getting all cubes from database...')
    cubequery = session.query(datadb.Cube).join(datadb.PipelineInfo,datadb.PipelineVersion,datadb.IFUDesign)\
        .filter(datadb.PipelineVersion.version==version,datadb.IFUDesign.nfiber != 7)
    cubes = cubequery.all()      
 
    # get all plate types (for right now..eventually build plate table and summary table)
    current_app.logger.info('Getting plate types...') 
    galcubequery = cubequery.join(datadb.FitsHeaderValue,datadb.FitsHeaderKeyword).filter(datadb.FitsHeaderKeyword.label=='MNGTRG1',datadb.FitsHeaderValue.value != '0')
    starcubequery = cubequery.join(datadb.FitsHeaderValue,datadb.FitsHeaderKeyword).filter(datadb.FitsHeaderKeyword.label=='MNGTRG2',datadb.FitsHeaderValue.value != '0')
    anccubequery = cubequery.join(datadb.FitsHeaderValue,datadb.FitsHeaderKeyword).filter(datadb.FitsHeaderKeyword.label=='MNGTRG3',datadb.FitsHeaderValue.value != '0')    
    galcubes = galcubequery.all()
    starcubes = starcubequery.all()
    anccubes = anccubequery.all()
    unigals = list(set([cube.plate for cube in galcubes]))
    unistars = list(set([cube.plate for cube in starcubes]))
    uniancs = list(set([cube.plate for cube in anccubes]))
    
    plates = list(set([cube.plate for cube in cubes]))
    types = ['Stellar' if plate in unistars else 'Galaxy' if plate in unigals else 'Ancillary' if plate in uniancs else None for plate in plates]
        
    #plclass = {cube.plate:cube.plateclass for cube in cubes}
    #types = [val.type for key,val in plclass.iteritems()]

    index['cubes'] = galcubes
    index['plates'] = plates
    index['types'] = types
    index['labels'] = ['Galaxy', 'Stellar', 'Ancillary', None]
    
    current_app.logger.info('Passing to template...')

    return render_template("index.html", **index)