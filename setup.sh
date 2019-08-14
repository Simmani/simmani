#!/usr/bin/env bash
if [ -z $HAMMER_ENVIRONMENT_CONFIGS ]
then
  git config --global submodule.tools/hammer.update none
  git config --global submodule.tools/hammer-cad-plugins.update none
  git config --global submodule.tools/hammer-adept-plugins.update none
fi
git submodule update --init --recursive
if [ -z $HAMMER_ENVIRONMENT_CONFIGS ]
then
  git config --global --unset submodule.tools/hammer.update
  git config --global --unset submodule.tools/hammer-cad-plugins.update
  git config --global --unset submodule.tools/hammer-adept-plugins.update
fi
