#!/bin/bash
sudo chown -R $UID:0 /github/home /opt/pyenv
exec "$@"
