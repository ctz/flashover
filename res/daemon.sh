#!/bin/sh
cd /var/www-flashover/flashover/
python backend.py > /var/log/flashover/log 2>&1
