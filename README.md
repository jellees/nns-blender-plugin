# Nintendo Nitro System Blender Plugin

A plugin for blender 2.8 that is able to export intermediate model format (.imd) for use in homebrew projects or other NDS related activities.

## How to install

Download the latest zip from releases and extract it in the addons folder.

## Instructions

For materials to be exported correctly you need to use the PrincipledBSDF node (the default node). The base color (diffuse) and emission are used for export. Other materials can be configured in the "NNS Material Options" panel at the materials tab.

Be sure to use nitro tga files for textures. All other formats will be ignored.

## Known problems

Normals appear to be 90 degrees rotated on conversion. A solution is being worked on. This does not affect your model in any way if you don't use lighting.