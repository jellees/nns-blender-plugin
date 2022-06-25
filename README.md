# Nintendo Nitro System Blender Plugin

A plugin for blender 2.8 that is able to export intermediate model format (.imd) for use in homebrew projects or other NDS related activities.

## How to install

Download the latest zip from releases and extract it in the addons folder. Alternatively you can also install the plugin from the addons window.

## Instructions

After installing the plugin, you can export your model to imd by going to the export tab and clicking on "Nitro IMD". You can add a material to your object by clicking on the "Create NNS Material" button in the material tab. Be aware that vertex colored models need a vertex color layer called "Col" to be present. Alternatlivey you can also use a PrincipledBSDF node with limited options.

Be sure to use nitro tga files for textures. All other formats will be ignored. You can generate nitro tga's by using Optipix or NitroPaint https://github.com/Garhoogin/NitroPaint/releases

## Material preview

You can preview your material by switching to lookdev mode or rendered mode. This feature aids you in crafting your material but it is not a 100% accurate rendering of what it will look like on the ds. Be sure to have a vertex color layer named "Col" when using vertex colored materials, otherwise your material will be black.

As for vertex lighting, the lights parameters can be changed in the the section called "NNS scene" in the panel on the right in the 3D view window, by default the light properties are similar to the ones in mario kart ds tracks.

Billboarding is supported but you have to play the animation to make it track the viewport camera, also if there are multiple 3D view windows on the screen, the objects will only track the first window's camera rotation.

## Exporting bones and animation

You can export your rigged model and the current active animation by enabling "export .ica" in the export window. You can influence the size-quality ratio by changing the tolerance and frame step mode. Be sure to set the node compression to none, otherwise no bones will be exported.

Please keep these points in mind when making a rig and animation:
* Make sure that each vertex is only part of one vertex group.
* Do not use extreme transforms on your mesh or armature (Like using a scale of 0.00002 for example). Apply them if needed.
* The length of the animation is set by the playback length of the scene.

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