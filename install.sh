#!/bin/bash
################################ USAGE #######################################

usage=$(
cat <<EOF
Usage:
$0 [OPTION]
-h, --help show this message.
-l, --local install the plugin locally (default).
-g, --global install the plugin globally.
-3, --rb3       install the plugin for rhythmbox 3 (default)
EOF
)

########################### OPTIONS PARSING #################################

#parse options
TMP=`getopt --name=$0 -a --longoptions=local,global,rb3,help -o l,g,3,h -- $@`

if [[ $? == 1 ]]
then
echo
echo "$usage"
    exit
fi

eval set -- $TMP

until [[ $1 == -- ]]; do
case $1 in
        -l|--local)
            LOCAL=true
            ;;
        -g|--global)
            LOCAL=false
            ;;
        -3|--rb3)
            RB=false
            ;;
        -h|--help)
            echo "$usage"
            exit
            ;;
    esac
shift # move the arg list to the next option or '--'
done
shift # remove the '--', now $1 positioned at first argument if any

#default values
LOCAL=${LOCAL:=true}
RB=${RB:=false}

########################## START INSTALLATION ################################


SCRIPT_NAME=`basename "$0"`
SCRIPT_PATH=${0%`basename "$0"`}
PLUGIN_PATH="${HOME}/.local/share/rhythmbox/plugins/szyrics/"
GLIB_SCHEME="org.gnome.rhythmbox.plugins.szyrics.gschema.xml"
SCHEMA_FOLDER="schema/"
GLIB_DIR="/usr/share/glib-2.0/schemas/"

#install the glib schema
echo "Installing the glib schema (password needed)"
sudo cp "${SCRIPT_PATH}${SCHEMA_FOLDER}${GLIB_SCHEME}" "$GLIB_DIR"
sudo glib-compile-schemas "$GLIB_DIR"

#install the plugin; the install path depends on the install mode
if [[ $LOCAL == true ]]
then
    echo "Installing plugin locally"

    #remove old dirs
    rm -r -f "$PLUGIN_PATH"
    #build the dirs
    mkdir -p $PLUGIN_PATH

    #copy the files
    cp -r "${SCRIPT_PATH}"* "$PLUGIN_PATH"

    #remove the install script from the dir (not needed)
    #rm "${PLUGIN_PATH}${SCRIPT_NAME}"

else
echo "Installing plugin globally"
    PLUGIN_PATH="/usr/lib/rhythmbox/plugins/szyrics/"
    DATA_PATH="/usr/share/rhythmbox/plugins/szyrics/"

    #remove old dirs
    sudo rm -r -f $PLUGIN_PATH
    sudo rm -r -f $DATA_PATH

    #build the dirs
    sudo mkdir -p $PLUGIN_PATH
    sudo mkdir -p $DATA_PATH
    
    #copy the files
    sudo cp "${SCRIPT_PATH}"*.py "$PLUGIN_PATH"
    sudo cp "${SCRIPT_PATH}"szyrics.plugin "$PLUGIN_PATH"szyrics.plugin

    sudo cp -r "${SCRIPT_PATH}"ui "$DATA_PATH"
    sudo cp -r "${SCRIPT_PATH}"img "$DATA_PATH"
fi

echo "Finished installing the plugin. Enjoy :]"