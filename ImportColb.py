bl_info = {
    "name": "Import .colb Sky Color Tables",
    "author": "Leo",
    "version": (1, 6),
    "blender": (4, 2, 0),
    "location": "View3D → Sidebar → N-Tab → Colb Sky",
    "description": "Apply .colb sky color table to selected sky/cloud mesh",
    "category": "Import-Export",
}

import bpy
import os
from pathlib import Path


# ============================================================
# GLOBAL PROPERTIES
# ============================================================
class ColbImportProps(bpy.types.PropertyGroup):
    filepath: bpy.props.StringProperty(
        name="Colb File",
        description="Path to the .colb file",
        subtype="FILE_PATH",
    )
    attribute_name: bpy.props.StringProperty(
        name="Color Attribute",
        description="Name for the vertex color attribute layer",
        default="SkyColor",
        maxlen=64,
    )
    uv_name: bpy.props.StringProperty(
        name="UV Layer",
        description="Name for the UV layer to write colors into",
        default="ColbUV",
        maxlen=64,
    )
    store_as_color: bpy.props.BoolProperty(
        name="Store as Vertex Color",
        description="Write colors into a color attribute layer",
        default=True,
    )


# ============================================================
# FORMAT CONSTANTS
# ============================================================
MAGIC = b"colb"
HEADER_SIZE = 16


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def srgb_to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def read_colb(filepath):
    try:
        data = Path(filepath).read_bytes()
    except OSError as e:
        raise RuntimeError(f"Cannot read file: {e}")

    if len(data) < HEADER_SIZE:
        raise RuntimeError(f"File too small ({len(data)} bytes).")

    magic = data[0:4]
    if magic != MAGIC:
        raise RuntimeError(f"Not a valid .colb file (magic: {magic!r}).")

    declared = int.from_bytes(data[8:10], "little")
    body = data[HEADER_SIZE:]

    colors = []
    for i in range(len(body) // 4):
        r, g, b, a = body[i * 4 : i * 4 + 4]
        colors.append((r, g, b, a))

    while len(colors) > declared and colors[0][3] == 0:
        colors.pop(0)

    return {
        "file_size": int.from_bytes(data[4:6], "little"),
        "declared": declared,
        "parsed": len(colors),
        "colors": colors,
    }


def apply_as_color_attribute(obj, colors, attr_name="SkyColor"):
    """Write colors into a BYTE_COLOR vertex attribute layer."""
    me = obj.data
    nv = len(me.vertices)
    n = len(colors)

    if nv != n:
        raise RuntimeError(
            f"Vertex count mismatch!\n"
            f"  Mesh has {nv} vertices\n"
            f"  .colb has {n} color entries\n"
            f"  Expected exact match."
        )

    linear = [
        (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a / 255.0)
        for (r, g, b, a) in colors
    ]

    for attr in list(me.color_attributes):
        if attr.name == attr_name:
            me.color_attributes.remove(attr)

    vcol = me.color_attributes.new(
        name=attr_name, type="BYTE_COLOR", domain="CORNER"
    )

    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            vcol.data[li].color = linear[vi]

    return nv


def apply_as_uv(obj, colors, uv_name="ColbUV"):
    """
    Write colors into a UV layer. Each vertex's color maps to a UV coordinate.
    
    The mapping:
      R → UV.x
      G → UV.y
      B → UV.z (stored as a second UV pair via a second layer)
      A → UV.w (stored as a second UV pair via a second layer)
    
    Creates TWO UV layers:
      - 'ColbUV'   → (R, G) per vertex
      - 'ColbUV2'  → (B, A) per vertex
    
    Game engines like Unity can read these as separate UV channels.
    """
    me = obj.data
    nv = len(me.vertices)
    n = len(colors)

    if nv != n:
        raise RuntimeError(
            f"Vertex count mismatch!\n"
            f"  Mesh has {nv} vertices\n"
            f"  .colb has {n} color entries\n"
            f"  Expected exact match."
        )

    # Remove existing UV layers we're about to recreate
    for uv in list(me.uv_layers):
        if uv.name in (uv_name, uv_name + "2"):
            me.uv_layers.remove(uv)

    # Create first UV layer: (R, G)
    uv1 = me.uv_layers.new(name=uv_name)
    # Create second UV layer: (B, A)
    uv2 = me.uv_layers.new(name=uv_name + "2")

    for i, (r, g, b, a) in enumerate(colors):
        # Convert to normalized 0-1 range
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0
        a_norm = a / 255.0

        # Set UV for this vertex across all loops that reference it
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                if vi == i:
                    uv1.data[li].uv = (r_norm, g_norm)
                    uv2.data[li].uv = (b_norm, a_norm)

    return nv


# ============================================================
# OPERATOR
# ============================================================
class IMPORT_OT_colb_apply(bpy.types.Operator):
    bl_idname = "import.colb_apply"
    bl_label = "Apply Colors to Mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = context.selected_objects
        if not selected:
            self.report({"ERROR"}, "No object selected. Select a mesh first.")
            return {"CANCELLED"}

        if len(selected) > 1:
            self.report({"ERROR"}, f"Multiple objects selected ({len(selected)}). Select exactly one.")
            return {"CANCELLED"}

        obj = selected[0]
        if obj.type != "MESH":
            self.report({"ERROR"}, f"'{obj.name}' is not a mesh. Select a mesh object.")
            return {"CANCELLED"}

        props = context.scene.colb_import_props
        filepath = props.filepath

        if not filepath or not os.path.isfile(filepath):
            self.report({"ERROR"}, "No valid .colb file selected. Click the folder icon next to the path field.")
            return {"CANCELLED"}

        try:
            info = read_colb(filepath)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        try:
            nv = apply_as_color_attribute(obj, info["colors"], props.attribute_name) if props.store_as_color else apply_as_uv(obj, info["colors"], props.uv_name)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        # success message
        transp_count = sum(1 for c in info["colors"] if c[3] == 0)
        mode = "vertex color" if props.store_as_color else f"UV ({props.uv_name} + {props.uv_name}2)"
        msg = f"Applied {info['parsed']} colors"
        if transp_count > 0:
            msg += f" ({transp_count} transparent)"
        msg += f" to '{obj.name}' ({nv} vertices) as {mode}."

        self.report({"INFO"}, msg)

        # switch viewport to vertex colors if that mode is active
        if props.store_as_color:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.shading.color_type = "VERTEX"

        return {"FINISHED"}


# ============================================================
# UI PANEL
# ============================================================
class VIEW3D_PT_colb_import(bpy.types.Panel):
    bl_label = "Import .colb"
    bl_idname = "VIEW3D_PT_colb_import"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Colb Sky"

    def draw(self, context):
        layout = self.layout
        props = context.scene.colb_import_props

        col = layout.column(align=True)
        col.label(text="Selected object:")
        if context.active_object and context.active_object.type == "MESH":
            col.label(text=context.active_object.name, icon="OBJECT_DATA")
            col.label(text="(Mesh)", icon="MESH_DATA")
        else:
            col.label(text="No mesh selected", icon="ERROR")

        col.separator()
        col.prop(props, "filepath", text="")
        col.separator()

        # Toggle: vertex color vs UV
        col.prop(props, "store_as_color", text="Store as Vertex Color")
        col.separator()

        # Show the relevant property based on toggle state
        if props.store_as_color:
            col.label(text="Color Attribute:")
            col.prop(props, "attribute_name", text="")
        else:
            col.label(text="UV Layer Names:")
            col.prop(props, "uv_name", text="First UV")
            # Second UV is auto-generated as uv_name + "2"

        col.separator()

        col.scale_y = 1.5
        col.operator("import.colb_apply", text="Apply Colors to Mesh", icon="CHECKMARK")
        col.scale_y = 1.0

        col.separator()

        # Info about what will be generated
        if props.store_as_color:
            col.label(text=f"→ Creates attribute: {props.attribute_name}", icon="COLOR")
        else:
            col.label(text=f"→ Creates UV layers: {props.uv_name} + {props.uv_name}2", icon="UV")


# ============================================================
# REGISTRATION
# ============================================================
classes = (
    ColbImportProps,
    IMPORT_OT_colb_apply,
    VIEW3D_PT_colb_import,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.colb_import_props = bpy.props.PointerProperty(type=ColbImportProps)


def unregister():
    del bpy.types.Scene.colb_import_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()