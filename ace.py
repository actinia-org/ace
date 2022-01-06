#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# ace - actinia command execution
#
# Original source: https://github.com/mundialis/actinia_core/blob/master/scripts/ace
#
# GRASS GIS parser support added by Markus Neteler to make it work with g.extension
#
#######
# actinia-core - an open source REST API for scalable, distributed, high
# performance processing of geographical data that uses GRASS GIS for
# computational tasks. For details, see https://actinia.mundialis.de/
#
# Copyright (c) 2018-2021 Sören Gebbert and mundialis GmbH & Co. KG
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#######


#%Module
#% description: Allows the execution of single GRASS GIS command or a list of GRASS GIS commands on an actinia REST service.
#% keyword: general
#% keyword: API
#% keyword: REST
#%End

#%flag
#% key: a
#% description: Request the version of the actinia server
#%end

#%flag
#% key: d
#% description: Dry run: just print the JSON request and do not send the generated request to the server
#%end

#%flag
#% key: l
#% description: List locations the user has access to
#%end

#%flag
#% key: m
#% description: List mapsets within specified location
#%end

#%flag
#% key: r
#% description: List raster maps of mapsets of specified location
#%end

#%flag
#% key: v
#% description: List vector maps of mapsets of specified location
#%end

#%flag
#% key: s
#% description: List STRDS of mapsets of specified location
#%end

#%option
#% key: grass_command
#% type: string
#% description: GRASS GIS command to be executed
#%end

#%option
#% key: script
#% type: string
#% description: Script to be executed
#% label: Script file from which all all commands will be executed on the actinia server
#%end

#%option
#% key: location
#% description: Location name
#% label: Use this location name for processing on the actinia server
#%end

#%option
#% key: mapset
#% description: Mapset name
#% label: Use this persistent mapset name for processing on the actinia server
#%end

#%option
#% key: list_jobs
#% options: all,accepted,running,terminated,finished,error
#% description: List all jobs of the user
#%end

#%option
#% key: info_job
#% description: Show information about a job (use job-ID)
#%end

#%option
#% key: kill_job
#% description: Kill a job (use job-ID)
#%end

#%option
#% key: create_location
#% description: Create new location with EPSG code
#% label: Create new location in the persistent database of the actinia server using the provided EPSG code, e.g.: create_location="latlon 4326"
#%end

#%option
#% key: delete_location
#% description: Delete specified location
#% label: Delete existing location from the actinia server
#%end

#%option
#% key: create_mapset
#% description: Create specified mapset in location
#% label: Create a new mapset in the persistent database of the actinia server using the specified location
#%end

#%option
#% key: delete_mapset
#% description: Delete existing mapset
#% label: Delete an existing mapset from the actinia server using the specified location
#%end

#%option
#% key: render_raster
#% description: Render raster map
#% label: Show a rendered image from a specific raster map
#%end

#%option
#% key: render_vector
#% description: Render vector map
#% label: Show a rendered image from a specific vector map
#%end

#%option
#% key: render_strds
#% description: Render STRDS
#% label: Show a rendered image from a specific STRDS
#%end

#% rules
#% requires: create_mapset, location
#% requires: delete_mapset, location
#% requires: -m, location
#% requires_all: -r, location, mapset
#% requires_all: -v, location, mapset
#% requires_all: -s, location, mapset
#%end

import re
import requests
import simplejson
import time
import sys
import os
import grass.script as grass
import subprocess
from pprint import pprint
from typing import List, Optional

__license__ = "GPLv3"
__author__ = "Soeren Gebbert"
__copyright__ = "Copyright 2018-2021, Soeren Gebbert"
__maintainer__ = "Markus Neteler"
__email__ = "neteler@mundialis.de"

"""
export ACTINIA_USER='demouser'
export ACTINIA_PASSWORD='gu3st!pa55w0rd'
export ACTINIA_URL='https://actinia.mundialis.de'
export ACTINIA_VERSION='v3'
"""

# Example script for actinia with import and export options
# grass78 ~/grassdata/nc_spm_08/user1/
import_export = """
g.region raster=elev@https://storage.googleapis.com/graas-geodata/elev_ned_30m.tif -p
r.univar map=elev
r.info elev
r.slope.aspect elevation=elev slope=slope_elev+COG
r.info slope_elev
"""

# Example script for actinia with export options
# grass78 ~/grassdata/nc_spm_08/user1/
export_script = """
# Example script for actinia shell interface
g.region raster=elevation -p
r.univar map=elevation
r.info elevation
r.slope.aspect -a elevation=elevation slope=slope_elev+GTiff
# r.mapcalc expression=slope_elev=100
r.info slope_elev
r.watershed elevation=elevation accumulation=acc+GTiff
r.info acc
r.neighbors input=elevation output=neighbour_elev+GTiff
r.info neighbour_elev
"""

# Default values
ACTINIA_USER = 'demouser'
ACTINIA_PASSWORD = 'gu3st!pa55w0rd'
ACTINIA_URL = 'https://actinia.mundialis.de'
ACTINIA_VERSION = 'v3'
ACTINIA_AUTH = (ACTINIA_USER, ACTINIA_PASSWORD)
LOCATION = None
MAPSET = None
DRY_RUN = False

PCHAIN = {
    "version": "1",
    "list": list()
}


def set_credentials():
    """Read the environmental variables and set the actinia url and credentials

    Returns:

    """
    global ACTINIA_USER, ACTINIA_PASSWORD, ACTINIA_URL, ACTINIA_AUTH, ACTINIA_VERSION

    act_user = os.getenv("ACTINIA_USER")
    act_pass = os.getenv("ACTINIA_PASSWORD")
    act_url = os.getenv("ACTINIA_URL")
    act_ver = os.getenv("ACTINIA_VERSION")

    if act_user is not None:
        ACTINIA_USER = act_user

    if act_pass is not None:
        ACTINIA_PASSWORD = act_pass

    if act_url is not None:
        ACTINIA_URL = act_url

    if act_ver is not None:
        ACTINIA_VERSION = act_ver

    ACTINIA_AUTH = (ACTINIA_USER, ACTINIA_PASSWORD)


def setup_location(location: str = None):
    """Setup the location from argument or the current GRASS GIS location

    Args:
        location: The optional location to be set globally

    """

    global LOCATION

    if location is not None:
        LOCATION = location
    else:
        LOCATION = grass.read_command("g.gisenv", get="LOCATION_NAME")


def actinia_version():
    """Returs the version of the actinia server

    Returns:
        The version of the actinia server

    """
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/version"
    r = requests.get(url, auth=ACTINIA_AUTH)
    print(r.text)


def list_user_jobs(type_: str):
    """List all jobs of the user of a all or a specific type

    Args:
        type_: The type of the job: all, accepted, running, terminated, finished, error

    """

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/resources/{ACTINIA_USER}"
    r = requests.get(url, json=PCHAIN, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    for entry in data["resource_list"]:
        if type_.lower() == "all":
            print(entry["resource_id"], entry["status"], entry["datetime"])
        else:
            if type_.lower() == entry["status"]:
                print(entry["resource_id"], entry["status"], entry["datetime"])


def show_user_job_info(resource_id: str):
    """Show information about a specific actinia job

    Args:
        resource_id: The resource id of the job

    """

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/resources/{ACTINIA_USER}/" \
          f"{resource_id}"
    r = requests.get(url, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    pprint(data)


def kill_user_job(resource_id: str):
    """Kill a running actinia job

    Args:
        resource_id: The resource id of the job

    """

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/resources/{ACTINIA_USER}" \
        f"/{resource_id}"
    r = requests.delete(url, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    pprint(data)


def list_user_locations():
    """List all locations the user has access to
    """

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations"
    r = requests.get(url, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    if "locations" in data:
        pprint(data["locations"])
    else:
        pprint(data)


def list_user_mapsets(location):
    """List all mapsets of a specific location
    """

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{location}/mapsets"
    r = requests.get(url, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    if "process_results" in data:
        pprint(data["process_results"])
    else:
        pprint(data)


def list_maps_of_mapsets(mapset: str, map_type: str):
    """List specific map types of a specific location/mapset

    Args:
        mapset: The mapset to list the maps from
        map_type: The map type: raster_layers, vector_layers, strds

    """
    # Read location and mapset
    # mapset = grass.read_command("g.mapset", "p").strip()

    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}/mapsets" \
        f"/{mapset}/{map_type}"
    r = requests.get(url, auth=ACTINIA_AUTH)

    data = simplejson.loads(r.text)
    if "process_results" in data:
        pprint(data["process_results"])
    else:
        pprint(data)


def create_persistent_location(location: str, epsg_code: str) -> None:
    """Creates a location in the user specific persistent database

    Args:
        location: The location to be created in the user specific persistent database
        epsg_code: The EPSG code that should be used to create the location

    """

    print(f"Trying to create location {location}")
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{location}"
    r = requests.post(url, auth=ACTINIA_AUTH, json={"epsg": epsg_code})
    data = simplejson.loads(r.text)
    pprint(data)


def delete_persistent_location(location: str) -> None:
    """Delete a location from the user specific persistent database

    Args:
        location: The location to be deleted from the user specific persistent database

    """

    print(f"Trying to delete location {location}")
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{location}"
    r = requests.delete(url, auth=ACTINIA_AUTH)
    data = simplejson.loads(r.text)
    pprint(data)


def create_persistent_mapset(mapset: str):
    """Creates a mapset in the user specific persistent database

    Args:
        mapset: The mapset to be created in the user specific persistent database

    """

    print(f"Trying to create mapset {mapset}")
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}/mapsets" \
        f"/{mapset}"
    r = requests.post(url, auth=ACTINIA_AUTH)
    data = simplejson.loads(r.text)
    pprint(data)


def delete_persistent_mapset(mapset: str):
    """Deletes a mapset from the user specific persistent database

    Args:
        mapset: The mapset of the user specific persistent database to delete

    """

    print(f"Trying to delete mapset {mapset}")
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}/mapsets" \
        f"/{mapset}"
    r = requests.delete(url, auth=ACTINIA_AUTH)
    data = simplejson.loads(r.text)
    pprint(data)


def show_rendered_map(map_name: str, map_type: str):
    """Show a rendered map with the size of 800x600 pixel

    Args:
        map_name: The name of the raster map with optional mapset (name@mapset)
    """

    if "@" in map_name:
        map_name, mapset = map_name.split("@")
    else:
        mapset = grass.read_command("g.mapset", "p").strip()

    print(f"Trying to render {map_type} map {map_name} of mapset {mapset}")
    url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}/mapsets" \
        f"/{mapset}/{map_type}/{map_name}/render?width=800&height=600"
    r = requests.get(url, auth=ACTINIA_AUTH)
    if r.status_code != 200:
        pprint(r.text)
    else:
        from PIL import Image
        import io

        fp = io.BytesIO(r.content)
        image = Image.open(fp)
        image.show()


def split_grass_command(grass_command: str):
    """Split grass command at spaces exluding spaces in quotes. Additional for
    e.g. r.mapcalc the quotes are removed from the GRASS option value if the
    value starts and ends with quotes

    Args:
        grass_command: A string of a GRASS GIS command
    Returns:
        The splitted GRASS GIS command needed for create_actinia_process
    """
    SPACE_MATCHER = re.compile(r" (?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)")
    EQUALS_MATCHER = re.compile(r"=(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)")

    tokens = SPACE_MATCHER.split(grass_command)
    for i, token in enumerate(tokens):
        if "=" in token and ("\'" in token or '\"' in token):
            par, val = EQUALS_MATCHER.split(token)
            if val.startswith(val[-1]):
                tokens[i] = "%s=%s" % (par, val.strip('\"').strip("\'"))
    return tokens


def execute_script(script: str, mapset: str = None):
    """Execute a script with GRASS GIS commands

    Args:
        script (str): The script path
        mapset: If mapset is set, then the processing will be performed in the mapset of the persistent user database
    """
    f = open(script, "r")
    lines = f.readlines()

    commands = list()

    for line in lines:
        line = line.strip()
        # Get all lines that have no comments
        if line and "#" not in line[:1]:
            tokens = split_grass_command(line)
            commands.append(tokens)

    send_poll_commands(commands=commands, mapset=mapset)


def send_poll_commands(commands: List[List[str]], mapset: str = None) -> None:
    """Create the actinia process chain, send it to the actinia server
    and poll for the result

    Args:
        commands: A list of GRASS commands from the command line or from a script
        mapset: If mapset is set, then the processing will be performed in the mapset of the persistent user database
    """
    for command in commands:
        p_chain = create_actinia_process(command)
        if p_chain:
            PCHAIN["list"].append(p_chain)

    if DRY_RUN is True:
        print(simplejson.dumps(PCHAIN, sort_keys=False, indent=2 * ' '))
        return

    if mapset:
        url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}/" \
            f"mapsets/{mapset}/processing_async"
    else:
        url = f"{ACTINIA_URL}/api/{ACTINIA_VERSION}/locations/{LOCATION}" \
            "/processing_async_export"

    print(url)
    print(PCHAIN)
    print(ACTINIA_USER)

    req = requests.post(url, json=PCHAIN, auth=ACTINIA_AUTH)
    if req.status_code not in [200, 201]:
        msg = ''
        try:
            data = simplejson.loads(req.text)
            if 'message' in data:
                msg = f": {data['message']}"
        except Exception:
            msg = req.text
        grass.fatal(_(f"ERROR posting to url '{url}'{msg}"))
    try:
        data = simplejson.loads(req.text)
    except Exception:
        grass.fatal(_(req.text))
        return

    print("Resource status", data["status"])

    poll_url = data["urls"]["status"]

    print("Polling:", poll_url)

    while True:
        r = requests.get(poll_url, auth=ACTINIA_AUTH)

        try:
            data = simplejson.loads(r.text)
            print("Resource poll status:", data["status"])
            print(data["message"])

            final_status = data["status"]
            if data["status"] == "finished" or data["status"] == "error" or data["status"] == "terminated":
                break
            time.sleep(1)
        except Exception as a:
            raise

    print("--------------------------------------------------------------------------")

    if r.status_code == 200:

        if final_status == "terminated":
            print(r.text)
            return

        for entry in data["process_log"]:
            if entry["stdout"]:
                print(entry["stdout"])
            if entry["stderr"][0]:
                pprint(entry["stderr"])
        pprint(data["urls"])
    else:
        print(r.text)


def create_actinia_process(command: List[str]) -> Optional[dict]:
    """Create an actinia command dict, that can be put into a process chain

    Args:
        command: The GRASS GIS command as a list of strings

    Returns:
        The actinia process dictionary
    """
    if not command:
        return None
    if '--help' in command:
        raise Exception("--help is not allowed inside grass_command: %s"
                        % (str(command)))

    if "--json" not in command:
        command.append("--json")

    proc = subprocess.Popen(args=command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE)
    (stdout_buff, stderr_buff) = proc.communicate()
    stdout_buff = stdout_buff.decode()
    stderr_buff = stderr_buff.decode()

    # print(stdout_buff)

    if proc.returncode != 0:
        raise Exception("Error while executing GRASS command: %s. \n"
                        "\n%s\n%s\n" % (str(command), stdout_buff, stderr_buff))
    try:
        actinia_proc = simplejson.loads(stdout_buff)
        return actinia_proc
    except Exception:
        raise


def is_grass_command(grass_command: str):
    """Check if the given command is a GRASS GIS command

    Args:
        grass_command: A string of a GRASS GIS command
    Returns:
        True if the command is a GRASS GIS command otherwise False
    """
    if grass_command.split('.')[0] in ["r", "v", "i", "t", "g", "r3"]:
        return True
    else:
        return False


def main():

    version = flags["a"]
    dry_run = flags["d"]
    list_locations = flags["l"]
    list_mapsets = flags["m"]
    list_raster = flags["r"]
    list_vector = flags["v"]
    list_strds = flags["s"]
    mapset = False

    grass_command = options["grass_command"]
    script = options["script"]

    list_jobs = options["list_jobs"]
    info_job = options["info_job"]
    location = options["location"]
    if options["mapset"]:
        mapset = options["mapset"]
    create_mapset = options["create_mapset"]
    delete_mapset = options["delete_mapset"]
    create_location = options["create_location"]
    delete_location = options["delete_location"]
    render_raster = options["render_raster"]
    render_vector = options["render_vector"]
    render_strds = options["render_strds"]
    kill_job = options["kill_job"]

    set_credentials()
    setup_location()

    global DRY_RUN
    if dry_run:
        DRY_RUN = True

    if version is True:
        actinia_version()
        return

    if create_location:
        create_persistent_location(create_location.split()[0], create_location.split()[1])
        return

    if delete_location:
        delete_persistent_location(delete_location)
        return

    ## DEBUGGER
    #import pdb; pdb.set_trace()

    if location:
        setup_location(location=location)
        if script:
            execute_script(script=script, mapset=mapset)
        elif list_mapsets:
            list_user_mapsets(location)
        elif list_raster and mapset is not False:
            list_maps_of_mapsets(mapset=mapset, map_type="raster_layers")
        elif list_vector and mapset is not False:
            list_maps_of_mapsets(mapset=mapset, map_type="vector_layers")
        elif list_strds and mapset is not False:
            list_maps_of_mapsets(mapset=mapset, map_type="strds")
        elif render_raster:
            show_rendered_map(map_name=render_raster, map_type="raster_layers")
        elif render_vector:
            show_rendered_map(map_name=render_vector, map_type="vector_layers")
        elif render_strds:
            show_rendered_map(map_name=render_strds, map_type="strds")
        elif create_mapset:
            create_persistent_mapset(mapset=create_mapset)
        elif delete_mapset:
            delete_persistent_mapset(mapset=delete_mapset)
        else:
            # TODO: fails with r3 (r.g. r3.info
            if is_grass_command(grass_command):
                send_poll_commands(commands=[split_grass_command(grass_command), ], mapset=mapset)
    elif list_jobs:
        if not list_jobs:
            list_jobs = "all"
        list_user_jobs(type_=list_jobs)
    elif info_job:
        show_user_job_info(resource_id=info_job)
    elif kill_job:
        kill_user_job(resource_id=kill_job)
    elif list_locations:
        list_user_locations()
    elif list_raster:
        list_maps_of_mapsets(mapset=list_raster, map_type="raster_layers")
    elif list_vector:
        list_maps_of_mapsets(mapset=list_vector, map_type="vector_layers")
    elif list_strds:
        list_maps_of_mapsets(mapset=list_strds, map_type="strds")
    elif render_raster:
        show_rendered_map(map_name=render_raster, map_type="raster_layers")
    elif render_vector:
        show_rendered_map(map_name=render_vector, map_type="vector_layers")
    elif render_strds:
        show_rendered_map(map_name=render_strds, map_type="strds")
    elif list_mapsets:
        list_user_mapsets(location)
    elif create_mapset:
        create_persistent_mapset(mapset=create_mapset)
    elif delete_mapset:
        delete_persistent_mapset(mapset=delete_mapset)
    elif script:
        execute_script(script=script, mapset=mapset)
    else:
        if len(sys.argv) > 1:
            # TODO: fails with r3 (r.g. r3.info
            if is_grass_command(grass_command):
                send_poll_commands(commands=[list(grass_command), ], mapset=mapset)
        else:
            actinia_version()


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
