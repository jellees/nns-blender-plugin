# Nintendo Nitro System Blender Plugin

A plugin for blender 2.8 that is able to export intermediate model format (.imd) for use in homebrew projects or other NDS related activities.

## How to install

Download the latest zip from releases and extract it in the addons folder. Alternatively you can also install the plugin from the addons window.

## Instructions

After installing the plugin, you can export your model to imd by going to the export tab and clicking on "Nitro IMD". You can add a material to your object by clicking on the "Create NNS Material" button in the material tab. Be aware that vertex colored models need a vertex color layer called "Col" to be present. Alternatlivey you can also use a PrincipledBSDF node with limited options.

Be sure to use nitro tga files for textures. All other formats will be ignored. You can generate nitro tga's by using Optipix or TGAConv https://garhoogin.com/mkds/tgaconv/

## Material preview

You can preview your material by switching to lookdev mode or rendered mode. This feature aids you in crafting your material but it is not a 100% accurate rendering of what it will look like on the ds. Be sure to have a vertex color layer named "Col" when using vertex colored materials, otherwise your material will be black.

## Exporting texture animation

You can export texture animation by animating the SRT values in the material and then enabling .ita for export.

## Troubleshooting

### Material doesn't have transparency (or wrong transparency) in blender

Under the settings tab of your material, you can choose the blend method. Please choose the appropriate blend method for your material. If your material doesn't use any kind of transparency or tranlucency, be sure to set it on opaque.

## Special thanks
* Stomatol for suggesting features and helping with shader nodes
* Gericom for technical knowledge on NNS and tristripping
* SGC for suggesting features
* PK dab for testing the plugin and suggesting features
* Riidefi for giving examples on how to make a plugin