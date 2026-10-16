# Majora's Mask (Grezzo) .Colb Format

<img width="1428" height="808" alt="Screenshot 2026-10-16 040207" src="https://github.com/user-attachments/assets/044d7096-cda0-4f5a-a75d-9b0f17112322" />

In sky.gar.lzs resides only a handful of cmb files for the tenkyu and kumo. But Ocarina Of Time had multiple for each sky color variation.
This took up unnecessary space, thus the .colb files were introduced.
In other words, instead of Ocarina of Time's approach of shipping multiple .cmb meshes per sky state (dawn, day, dusk, night), MM3D uses a single skydome and cloud mesh with color data stored in separate .colb files. These files can be swapped at runtime, letting the game transition between sky states without duplicating geometry. This repository provides a Blender addon to apply the color tables to extracted sky/cloud meshes.

<b>How to use the addon?</b>

Select either the tenkyu or kumo mesh (Not both) and use the 'Colb sky' toolbar to predetermine a .colb file.
Decide whether to store the color data inside two uv's or directly in the vertex color and click apply.
The uv storing option is for when you'd like to transition between the two. It also comes in handy for when you'd like to use it in other game engines as well.
You can simply create a shader that makes use of those uv coordinates.

<b>Important</b>

The mesh's vertices count needs to match exactly with the amount of color entries of the colb file.
There's three categories of sky meshes so pay close attention to which one you're using. (_cl, _dk or _fn)
Also, f.e. t00_dk_kumo_a0.cmb can come with two seperate meshes, it's necessary to merge them. (if they're not already.)
