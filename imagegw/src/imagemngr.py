#!/usr/bin/python

from pymongo import MongoClient
import json
from imageworker import dopull
import bson
import celery
import sys, os
import logging
import auth


logger = logging.getLogger('imagemngr')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)


class imagemngr:
  """
  This class handles most of the backend work for the image gateway.
  It uses a Mongo Database to track state, uses celery to dispatch work,
  and has public functions to lookup, pull and expire images.
  """

  def __init__(self, CONFIGFILE, logger=None):
      """
      Create an instance of the image manager.
      """
      with open(CONFIGFILE) as config_file:
          self.config = json.load(config_file)
      if 'Platforms' not in self.config:
          raise NameError('Platforms not defined')
      self.systems=[]
      self.tasks=[]
      self.task_image_id=dict()
      if 'Authentication' not in self.config:
          self.config['Authentication']="munge"
      self.auth=auth.authentication(self.config)

      for system in self.config['Platforms']:
          self.systems.append(system)
      # Connect to database
      if 'MongoDBURI' in self.config:
          client = MongoClient(self.config['MongoDBURI'])
          db=self.config['MongoDB']
          self.images=client[db].images
      else:
          raise NameError('MongoDBURI not defined')
      # Initialize data structures


  def isasystem(self,system):
      """Check if system is a valid platform."""
      if system in self.systems:
          return True
      else:
          return False

  def checkread(self,user,imageid):
      """Checks if the user has read permissions to the image. (Not Implemented)"""
      return True

  def resetexpire(self,imageid):
      """Reset the expire time.  (Not Implemented)."""
      # Change expire time for image
      return True


  def lookup(self,auth,image):
      """
      Lookup an image.
      Image is dictionary with system,itype and tag defined.
      """
      arec=self.auth.authenticate(auth)
      q={'system':image['system'],
        'itype':image['itype'],
        'tag':image['tag']}
      self.update_states()
      rec=self.images.find_one(q)
      # verify access
      return rec

  def isready(self,image):
      """
      Helper function to determine if an image is READY.
      """
      q={'system':image['system'],'itype':image['itype'],'tag':image['tag']}
      rec=self.images.find_one(q)
      if rec is not None and 'status' in rec and rec['status']=='READY':
          return True
      return False

  def new_image_record(self,auth,image):
      """
      Creates a new image in mongo.  If the image already exist it returns the mongo record.
      """
      record=self.lookup(auth,image)
      if record is not None:
          return record
      newimage={'format':'ext4',#<ext4|squashfs|vfs>
          'arch':'amd64', #<amd64|...>
          'os':'linux', #<linux|...>
          'location':'', #<urlencoded location, interpretation dependent on remotetype>
          'remotetype':'dockerv2', #<file|dockerv2|amazonec2>
          'ostcount':'0', #<integer, number of OSTs to per-copy of the image>
          'replication':'1', #<integer, number of copies to deploy>
          'userAcl':[],
          'status':'UNKNOWN',
          'groupAcl':[]}
      for p in image:
          newimage[p]=image[p]
      self.images.insert(newimage)
      return newimage


  def pull(self,auth,request,delay=True,TESTMODE=0):
      """
      pull the image
      Takes an auth token, a request object
      Optional: deplay=True/False
      """
      logger.debug('pull called TM=%d'%TESTMODE) # will print a message to the console
      if self.isready(request)==False:
          rec=self.new_image_record(auth,request)
          id=rec.pop('_id',None)
          logger.debug("Setting state")
          self.update_mongo_state(id,'ENQUEUED')
          if delay:
              logger.debug("Calling do pull with queue=%s"%(request['system']))
              pullreq=dopull.apply_async([request],queue=request['system'],
                    kwargs={'TESTMODE':TESTMODE})
          else: # Fake celery
              dopull(request)
              pullreq=id
          self.task_image_id[pullreq]=id
          self.tasks.append(pullreq)
          #def pullImage(options, config[''], repo, tag, cacert=None, username=None, password=None):
          #pullImage(None, 'https://registry.services.nersc.gov', 'lcls_xfel_edison', '201509081609', cacert='local.crt')
      else:
        rec=self.new_image_record(auth,request)
        id=rec.pop('_id',None)
      return id

  def update_mongo_state(self,id,state):
      """
      Helper function to set the mongo state for an image with _id==id to state=state.
      """
      if state=='SUCCESS':
          state='READY'
      self.images.update({'_id':id},{'$set':{'status':state}})

  def get_state(self,id):
      """
      Lookup the state of the image with _id==id in Mongo.  Returns the state."""
      self.update_states()
      return self.images.find_one({'_id':id},{'status':1})['status']


  def update_states(self):
      """
      Update the states of all active transactions.
      """
      logger.debug("Update_states called")
      # TODO: Remove tasks that are in the READY state.
      for req in self.tasks:
          state='PENDING'
          if isinstance(req,celery.result.AsyncResult):
              state=req.state
              #logger.debug(" state=%s"%state)
          elif isinstance(req,bson.objectid.ObjectId):
              print "Non-Async"
          #print self.task_image_id[req]
          self.update_mongo_state(self.task_image_id[req],state)
          #self.images.update({'_id':self.task_image_id[req]},{'$set':{'status':req.state}})
          #print self.images.find_one()


  def expire(self,auth,system,type,tag,id):
      """Expire an image.  (Not Implemented)"""
      # Do lookup
      resp=dict()
      return resp

def usage():
    """Print usage"""
    print "Usage: imagemngr <lookup|pull|expire>"
    sys.exit(0)

if __name__ == '__main__':
    configfile='test.json'
    if 'CONFIG' in os.environ:
        configfile=os.environ['CONFIG']
    m=imagemngr(configfile)
    sys.argv.pop(0)
    if len(sys.argv)<1:
        usage()
        sys.exit(0)
    command=sys.argv.pop(0)
    if command=='lookup':
        if len(sys.argv)<3:
            usage()
    elif command=='pull':
        if len(sys.argv)<3:
            usage()
        print "pull"
        req=dict()
        (req['system'],req['itype'],req['tag'])=sys.argv
        m.pull('good',req)
    else:
        print "Unknown command %s"%(command)
        usage()
