#!/usr/bin/python

import json
import os
import sys
import socket
import time
from shifter_imagegw import imagemngr
from shifter_imagegw import app, AUTH_HEADER, mgr
import logging
from flask import Flask, Blueprint, request, Response, url_for, jsonify

"""
Shifter, Copyright (c) 2015, The Regents of the University of California,
through Lawrence Berkeley National Laboratory (subject to receipt of any
required approvals from the U.S. Dept. of Energy).  All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
 1. Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.
 3. Neither the name of the University of California, Lawrence Berkeley
    National Laboratory, U.S. Dept. of Energy nor the names of its
    contributors may be used to endorse or promote products derived from this
    software without specific prior written permission.`

See LICENSE for full text.
"""


# For RESTful Service
@app.errorhandler(404)
def not_found(error=None):
    app.logger.warning("404 return")
    message = {
            'status': 404,
            'error': str(error),
            'message': 'Not Found: ' + request.url,
    }
    resp = jsonify(message)
    resp.status_code = 404
    return resp

@app.route('/')
def help():
    return "{lookup,pull,expire}"

def create_response(rec):
    resp={}
    for field in ('id','system','itype','tag','status','userAcl','groupAcl','ENV','ENTRY','WORKDIR','last_pull'):
        try:
            resp[field]=rec[field]
        except KeyError,e:
            resp[field]='MISSING'
    return resp

# Lookup image
# This will lookup the status of the requested image.
@app.route('/api/list/<system>/', methods=["GET"])
def list(system):
    auth=request.headers.get(AUTH_HEADER)
    app.logger.debug("list system=%s"%(system))
    try:
        session=mgr.new_session(auth,system)
        records=mgr.list(session,system)
        if records==None:
            return not_found('image not found')
    except:
        app.logger.exception('Exception in list')
        return not_found('%s'%(sys.exc_value))
    li=[]
    for rec in records:
        li.append(create_response(rec))
    resp={'list':li}
    return jsonify(resp)


# Lookup image
# This will lookup the status of the requested image.
@app.route('/api/lookup/<system>/<type>/<path:tag>/', methods=["GET"])
def lookup(system,type,tag):
    auth=request.headers.get(AUTH_HEADER)
    app.logger.debug("lookup system=%s type=%s tag=%s auth=%s"%(system,type,tag,auth))
    i={'system':system,'itype':type,'tag':tag}
    try:
        session=mgr.new_session(auth,system)
        rec=mgr.lookup(session,i)
        if rec==None:
            return not_found('image not found')
    except:
        app.logger.exception('Exception in lookup')
        return not_found('%s %s'%(sys.exc_type,sys.exc_value))
    return jsonify(create_response(rec))
# {
# 	"tag": "ubuntu:15.04",
# 	"id": "<long random string of hexadecimal characters>",
# 	"system": "edison",
# 	"status": "ready",
# 	"userAcl": [],
# 	"groupAcl": [],
# 	"ENV": [
# 		"PATH=/usr/bin:bin"
# 	],
# 	"ENTRY": ""
# }

# Pull image
# This will pull the requested image.
@app.route('/api/pull/<system>/<type>/<path:tag>/', methods=["POST"])
def pull(system,type,tag):
    auth=request.headers.get(AUTH_HEADER)
    app.logger.debug("pull system=%s type=%s tag=%s"%(system,type,tag))
    i={'system':system,'itype':type,'tag':tag}
    try:
        session=mgr.new_session(auth,system)
        rec=mgr.pull(session,i)
        app.logger.debug(rec)
    except:
        app.logger.exception('Exception in pull')
        return not_found('%s %s'%(sys.exc_type,sys.exc_value))
    return jsonify(create_response(rec))

# expire image
# This will expire an image which removes it from the cache.
@app.route('/api/expire/<system>/<type>/<tag>/<id>/', methods=["GET"])
def expire(system,type,tag,id):
    auth=request.headers.get(AUTH_HEADER)
    app.logger.debug("expire system=%s type=%s tag=%s"%(system,type,tag))
    try:
        session=mgr.new_session(auth,system)
        resp=mgr.expire(session,system,type,tag,id)
    except:
        app.logger.exception('Exception in expire')
        return not_found()
    return jsonify(resp)



def main():
    app.run(debug=DEBUG_FLAG, host='0.0.0.0', port=LISTEN_PORT, threaded=True)

if __name__ == '__main__':
    main()
