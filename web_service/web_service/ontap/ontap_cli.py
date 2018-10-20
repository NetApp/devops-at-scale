# vim: set expandtab:ts=4:sw=4:softtabstop=4
'''
NetApp-Jenkins Integration Scripts
   This script was developed by NetApp to help demonstrate NetApp
   technologies.  This script is not officially supported as a
   standard NetApp product.

Purpose: Script to interface with NSLM API services and Kubernetes to:
            1) create ONTAP volume and associated Kubernetes PV/PVC
            2) create ONTAP snapshot
            3) create ONTAP clone and associated Kubernetes PV/PVC
            4) list resources (volumes, snapshots, clones)
            5) delete resources

Usage:   %> ontap.py <args>

Author:  Laurent Nicolas (laurentn@netapp.com)

NETAPP CONFIDENTIAL
-------------------
Copyright 2016, 2017 NetApp, Inc. All Rights Reserved.
NOTICE: All information contained herein is, and remains the property
of NetApp, Inc.  The intellectual and technical concepts contained
herein are proprietary to NetApp, Inc. and its suppliers, if applicable,
and may be covered by U.S. and Foreign Patents, patents in process, and are
protected by trade secret or copyright law. Dissemination of this
information or reproduction of this material is strictly forbidden unless
permission is obtained from NetApp, Inc.
'''
import abc
import argparse
import json
import os
import sys
import yaml
from ontap_apis.ontap_apis import Aggregate, APIServer, Volume
from ontap_service import OntapService

#from kub.KubernetesAPI import KubernetesAPI

class Base(object):
    ''' base class for common functions '''

    @abc.abstractmethod
    def __init__(self):
        ''' '''
        self.parser_help = ""
        self.args = []

    def check_args(self, required_attrs):
        ''' verify mandatory parameters are present '''
        msg = list()
        for attr in vars(self.args):
            if getattr(self.args, attr) is None and attr in required_attrs:
                msg.append("--%s is required" % attr)

        if msg:
            print("ERROR: required argument(s):")
            print("    " + "\n    ".join(msg))
            print(self.parser_help)
            sys.exit(1)

    def get_cmd(self, prefix, action, name):
        ''' build cmd and check it exists '''
        cmd = "%s_%s" % (prefix, action)
        if not hasattr(self, cmd):
            print("Unrecognized command %s" % action)
            print("Supported %ss:" % name, " ".join(self.get_cmds(prefix)))
            sys.exit(1)
        return cmd

    def get_cmds(self, prefix):
        ''' print list of defined commands '''
        prefix = "%s_" % prefix
        cmds = list()
        for method in dir(self):
            if method.startswith(prefix):
                cmds.append(method[len(prefix):])
        return cmds

    def construct_json_response(self, statuses):
        data = list()
        for status in statuses:
            data.append(self.format_status(status))

        if self.args.json:
            print(json.dumps(data))
        else:
            print("\n".join(data))

    def format_status(self, status):
        if self.args.json:
            json = {
                'code': status['code'],
                'status': status['status'],
                'message': status['message'],
                'error': status['error_message'],
                'resource': status['resource'],
                'resource_name': status['resource_name']
            }
            return json

        msg = ""
        if status['message']:
            msg = status['message']
        if status['error_message']:
            msg = status['error_message']

        if 'time' in status:
            print(status['resource_name'], "Time:", status['time'])

        return "status: %s for %s resource %s: %s" % \
            (status['status'], status['resource'], status['resource_name'], msg)


    def set_status(self, code, resource_type, resource_name, error=""):
        status = dict()
        status['resource'] = resource_type
        status['resource_name'] = resource_name
        status['code'] = code
        status['error_message'] = error
        if code == 200:
            status['status'] = "SUCCESS"
            status['message'] = "%s %s already exists" % (resource_type, resource_name)
        elif code == 201:
            status['status'] = "COMPLETED"
            status['message'] = "%s %s created successfully" % (resource_type, resource_name)
        else:
            status['status'] = "FAILED"
            status['message'] = ""

        return status

class ONTAPCmds(Base):
    ''' top level dispatcher for list, create, delete commands '''

    def __init__(self, start=True):
        ''' set parser amd call second level dispatcher '''
        prefix = 'cmds'
        what = 'command'
        self.parse_args()
        if not start:
            return
        # get parms from yaml configuration file
        self.read_args()
        cmd = self.get_cmd(prefix, self.args.action, what)
        # check for mandatory parameters
        required_attrs = ['api', 'apiuser', 'apipass']
        self.check_args(required_attrs)
        # execute command
        getattr(self, cmd)()

    def find_config_file(self):
        ''' find yaml configuration file"
            1) from command line
            2) from local directory
            3) from $JENKINS_HOME
        '''
        if self.args.config_file is not None:
            if os.path.exists(self.args.config_file):
                return self.args.config_file
        config_file = "ontap_config.yaml"
        if os.path.exists(config_file):
            return config_file
        jenkins_home = os.environ.get("JENKINS_HOME", None)
        if jenkins_home:
            config_file = os.path.join(jenkins_home, "ontap_config.yaml")
            if os.path.exists(config_file):
                return config_file
        return None

    def read_args(self):
        ''' read args from yaml file is not present on command line '''
        config_path = self.find_config_file()
        if config_path:
            # print("Using configuration file: %s" % config_path)
            with open(config_path) as config_file:
                config = yaml.load(config_file)
            for attr in vars(self.args):
                if getattr(self.args, attr) is None:
                    if attr in config:
                        setattr(self.args, attr, config[attr])

    def parse_args(self):
        ''' read and parse command line arguments '''
        parser = argparse.ArgumentParser(description='Passing variables to the program')
        parser.add_argument('-ag', '--aggr_name', help='Aggregate to create or clone from')
        parser.add_argument('-vs', '--svm_name', help='Select SVM')
        parser.add_argument('-s', '--vol_size', help='Size of Volume in MB')
        parser.add_argument('-v', '--vol_name', help='Volume to create or clone from')
        parser.add_argument('-sn', '--snapshot_name', help='Snapshot to create or delete')
        parser.add_argument('-cl', '--clone_name', help='Clone to create or delete')
        parser.add_argument('-a', '--api', help='API server IP:port')
        parser.add_argument('-apiuser', '--apiuser', help='Add APIServer Username')
        parser.add_argument('-apipass', '--apipass', help='Add APIServer Password')
        parser.add_argument('-uid', '--uid', help='Add User ID')
        parser.add_argument('-gid', '--gid', help='Add Group ID')
        parser.add_argument('-cf', '--config_file', help='Configuration file for parameters')
        parser.add_argument('-j', '--json', help='Format output in JSON', action='store_true')
        parser.add_argument('action')
        self.parser_help = parser.format_help()
        self.args, self.other_args = parser.parse_known_args()

    def cmds_list(self):
        ''' dispatcher for list commands '''
        ListCmds(self.args, self.other_args)

    def cmds_create(self):
        ''' dispatcher for create commands '''
        CreateCmds(self.args, self.other_args)

    def cmds_delete(self):
        ''' dispatcher for delete commands '''
        DeleteCmds(self.args, self.other_args)


class ListCmds(Base):
    ''' support for list commands:
        list volumes
        list snapshots, clones, ...
    '''

    def __init__(self, args, other_args):
        prefix = 'list'
        what = 'target'
        self.parse_args(args, other_args)
        cmd = self.get_cmd(prefix, self.args.subaction, what)
        # execute command
        getattr(self, cmd)()

    def parse_args(self, args, leftover):
        ''' read and parse command line arguments '''
        parser = argparse.ArgumentParser(description='Passing variables to the program')
        parser.add_argument('subaction', metavar='list subcommand')
        self.args = parser.parse_args(leftover, args)
        self.parser_help = parser.format_help()

    def list_svms(self):
        ''' list all svms for svm '''
        api_server = APIServer(self.args.api, self.args.apiuser, self.args.apipass)
        svms = api_server.get_svms()
        svms = svms['result']['records']
        for svm in svms:
            print(svm['name'])

    def list_aggregates(self):
        ''' list all aggregates for svm '''
        api_server = APIServer(self.args.api, self.args.apiuser, self.args.apipass)
        aggregates = api_server.get_aggrs()
        aggregates = aggregates['result']['records']
        for aggregate in aggregates:
            print(aggregate['name'])

    def list_volumes(self):
        ''' list all volumes for an aggregate '''
        args = self.args
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        try:
            volumes = ontap.get_volume_list()
        except IOError as exc:
            print("Error:", exc.errno, exc.strerror, exc.filename)
            return
        if volumes:
            for volume in volumes:
                if not volume['clone_parent_key']:
                    print(volume['name'])
        else:
            print("%s does not have any volume" % args.aggr_name)

    def list_clones(self):
        ''' list all clones for a volume '''
        self.check_args(["vol_name"])
        args = self.args
        api_server = APIServer(args.api, args.apiuser, args.apipass)
        aggregate = Aggregate(args.svm_name, args.aggr_name, api_server)
        volume = Volume(args.vol_name, aggregate)
        clones = volume.get_clones()
        clones = clones['result']['records']
        for clone in clones:
            print(clone['name'])
        if not clones:
            print("%s does not have any clone" % args.vol_name)

    def list_snapshots(self):
        ''' list all snapshots for a volume '''
        self.check_args(["vol_name"])
        args = self.args
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        try:
            snapshots, error_message = ontap.get_snapshot_list(args.vol_name)
        except IOError as exc:
            if "Reason: Volume not online." in exc.filename:
                print("Error: %s is not online" % args.vol_name)
            else:
                print("Error:", exc.errno, exc.strerror, exc.filename)
            return
        if snapshots:
            print(snapshots)
        if not snapshots:
            print("%s does not have any snapshot" % args.vol_name)
        if error_message:
            print("ERROR:", error_message)

class CreateCmds(ONTAPCmds):
    ''' support for create commands:
        create volumes
        create snapshots, clones, ...
    '''

    def __init__(self, args, other_args):
        prefix = 'create'
        what = 'target'
        self.parse_args(args, other_args)
        cmd = self.get_cmd(prefix, self.args.subaction, what)
        # check for mandatory parameters
        self.check_args(["vol_name"])
        # execute command
        getattr(self, cmd)()

    def parse_args(self, args, leftover):
        ''' read and parse command line arguments '''
        parser = argparse.ArgumentParser(description='Passing variables to the program')
        parser.add_argument('subaction', metavar='list target')
        self.args = parser.parse_args(leftover, args)
        self.parser_help = parser.format_help()

    def create_volume(self):
        ''' API service call to create a new volume, or use an existing volume '''
        args = self.args
        self.check_args(["vol_size"])
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        status, vol_size = ontap.create_volume(args.vol_name, args.vol_size, args.uid, args.gid, args.export_policy)
        print("Create volume", status, vol_size)

    def create_snapshot(self):
        ''' create ONTAP snapshot for a volume '''
        args = self.args
        self.check_args(["snapshot_name"])
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        status = ontap.create_snapshot(args.vol_name, args.snapshot_name)
        print("Create snapshot", status)

    def create_clone(self):
        ''' API service call to clone a snapshot, or use an existing clone '''
        args = self.args
        self.check_args(["clone_name", "snapshot_name"])
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        status, vol_size = ontap.create_clone(args.vol_name, args.uid, args.gid,
                                              args.clone_name, args.snapshot_name)
        print("Create clone", status, vol_size)

class DeleteCmds(Base):
    ''' support for list commands:
        list volumes
        list snapshots, clones, ...
    '''

    def __init__(self, args, other_args):
        prefix = 'delete'
        what = 'target'
        self.parse_args(args, other_args)
        cmd = self.get_cmd(prefix, self.args.subaction, what)
        # check for mandatory parameters
        self.check_args(["vol_name"])
        # execute command
        getattr(self, cmd)()

    def parse_args(self, args, leftover):
        ''' read and parse command line arguments '''
        parser = argparse.ArgumentParser(description='Passing variables to the program')
        parser.add_argument('subaction', metavar='list target')
        self.args = parser.parse_args(leftover, args)
        self.parser_help = parser.format_help()

    def delete_clone(self):
        ''' delete one clone for a volume '''
        self.check_args(["clone_name"])
        args = self.args
        api_server = APIServer(args.api, args.apiuser, args.apipass)
        aggregate = Aggregate(args.svm_name, args.aggr_name, api_server)
        volume = Volume(args.vol_name, aggregate)
        status, error_message, error_message2 = volume.delete_clone(args.clone_name)
        if status != "COMPLETED":
            print("Error failed to delete %s" % args.clone_name, error_message, error_message2)
        else:
            print("Deleted %s" % args.clone_name)

    def delete_clones(self):
        ''' delete all clones for a volume '''
        args = self.args
        api_server = APIServer(args.api, args.apiuser, args.apipass)
        aggregate = Aggregate(args.svm_name, args.aggr_name, api_server)
        volume = Volume(args.vol_name, aggregate)
        deleted_clones, undeleted_clones = volume.delete_all_clones()
        for deleted_clone in deleted_clones:
            print("Deleted %s" % deleted_clone)
        for undeleted_clone in undeleted_clones:
            print("Failed to delete %s" % undeleted_clone)

    def delete_snapshot(self):
        ''' delete snapshot for a volume '''
        self.check_args(["snapshot_name"])
        args = self.args
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        status = ontap.delete_snapshot(args.vol_name, args.snapshot_name)
        if status[0]['status'] != "COMPLETED":
            print("Error failed to delete %s" % args.snapshot_name, status[0]['error_message'])
        else:
            print("Deleted %s" % args.snapshot_name)

    def delete_volume(self):
        ''' unmount, offline, and delete volume '''
        args = self.args
        api_credentials = {'api_server': args.api, 'username': args.apiuser, 'password': args.apipass}
        ontap = OntapService(api_credentials, args.svm_name, args.aggr_name)
        status = ontap.delete_volume(args.vol_name)
        print(status)
        if status[0]['status'] != "COMPLETED":
            print("Error failed to delete %s" % args.vol_name, status[0]['error_message'])
        else:
            print("Deleted %s" % args.vol_name)


if __name__ == '__main__':
    ONTAPCmds()
