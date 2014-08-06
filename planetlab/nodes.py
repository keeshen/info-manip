#! /usr/bin/python

import xmlrpclib

api_server = xmlrpclib.ServerProxy('https://www.planet-lab.org/PLCAPI/')

auth = {}
auth['Username'] = 'qks@umich.edu'
auth['AuthString'] = 
auth['AuthMethod']  = 

slice_data = {}
slice_data['name'] = 'michigan_nsrg'
nodes = api_server.GetSlices(auth, [slice_data['name']], 
    ['node_ids'])[0]['node_ids']
node_hostnames = [node['hostname'] for node in api_server.GetNodes(auth, nodes,
  ['hostname'])]
print node_hostnames

with open('node_hostnames.txt','w') as fwtr:
  for n in node_hostnames: fwtr.write('%s\n' % n)
