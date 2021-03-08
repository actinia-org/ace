#!/usr/bin/env bash

############################################################################
#
# MODULE:       ace test script
# AUTHOR(S):    Soeren Gebbert
#
# Original source: https://github.com/mundialis/actinia_core/blob/master/scripts/ace_test.sh
#
# PURPOSE:      This script contains commands that can be executed in a nc_spm_08 location
#               to the the ace command and its features
#
# COPYRIGHT:    (C) 2018-2021 by Sören Gebbert and mundialis GmbH & Co. KG
#
#               This program is free software under the GNU General Public
#               License (>=v3). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################

# halt on error
set -e

ace="python3 ../ace.py"

# List all maps in the search path of the PERMANENT mapset of the current location in actinia server
${ace} location="nc_spm_08" grass_command="g.list raster"
# List all mapsets of location nc_spm_08
${ace} location="nc_spm_08" -m
# List all raster layers in PERMANENT mapset of location nc_spm_08
${ace} location="nc_spm_08" mapset="PERMANENT" -r
# List all vector layers in PERMANENT mapset of location nc_spm_08
${ace} location="nc_spm_08" mapset="PERMANENT" -v
# List all strds layers in PERMANENT mapset of location nc_spm_08
${ace} location="nc_spm_08" mapset="PERMANENT" -s

# Create some commands with import and export options
cat << EOF > /tmp/commands.sh
# Import the web resource and set the region to the imported map
g.region raster=elev@https://storage.googleapis.com/graas-geodata/elev_ned_30m.tif -ap
# Compute univariate statistics
r.univar map=elev
r.info elev
# Compute the slope of the imported map and export it as Cloud Optimized GeoTIFF
r.slope.aspect elevation=elev slope=slope_elev+COG
r.info slope_elev
EOF

# Run the commands in an ephemeral location/mapset based in location nc_spm_08
${ace} location="nc_spm_08" script="/tmp/commands.sh"

#####################
# Persistent commands

# Create a new mapset in the persistent user database
${ace} location="nc_spm_08" create_mapset="test_mapset"
# Run the commands in the new persistent mapset
${ace} location="nc_spm_08" mapset="test_mapset" script="/tmp/commands.sh"
# Show all raster maps in test_mapset
${ace} location="nc_spm_08" mapset="test_mapset" grass_command="g.list type=raster mapset=test_mapset"
# Show information about raster map elev and slope_elev
${ace} location="nc_spm_08" mapset="test_mapset" grass_command="r.info elev@test_mapset"
${ace} location="nc_spm_08" mapset="test_mapset" grass_command="r.info slope_elev@test_mapset"
# Show all raster maps in test_mapset
${ace} location="nc_spm_08" mapset="test_mapset" -r
# Delete the test_mapset
${ace} location="nc_spm_08" delete_mapset="test_mapset"
