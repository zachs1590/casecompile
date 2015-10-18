#!/bin/sh
PYEX=../env/bin/python
if [ ! -x $PYEX ]; then
	PYEX=../$PYEX
fi
PYMODULE=$1
shift
APPNAME=`cat appname.txt`
export DJANGO_SETTINGS_MODULE=${APPNAME}.settings
$PYEX -c "import ${APPNAME}.tools.$PYMODULE" $@
