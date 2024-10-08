"""Import shaders."""

import bpy
import logging
import pathlib


from . import shader
from . import utils


def create_material(
    material_name: str,
    texture_file_path: pathlib.Path,
    *,
    has_alpha: bool,
) -> bpy.types.Material:
    """Create a material with the given texture file."""
    material = bpy.data.materials.get(material_name, None)

    if material is None:
        material = bpy.data.materials.new(name=material_name)

        image = bpy.data.images.get(texture_file_path.name)
        if image is None:
            image = bpy.data.images.load(texture_file_path.as_posix())
        material.use_nodes = True

        image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
        image_node.image = image

        principled_bsdf = material.node_tree.nodes.get('Principled BSDF')
        material.node_tree.links.new(image_node.outputs[0], principled_bsdf.inputs[0])
        principled_bsdf.inputs[2].default_value = 0.5
        principled_bsdf.inputs[12].default_value = 0.0

        if image.depth == 32:
            material.node_tree.links.new(image_node.outputs[1], principled_bsdf.inputs[4])
            material.blend_method = 'HASHED'

        specular_file_path = pathlib.Path(
            texture_file_path.parent,
            texture_file_path.stem + " specular" + texture_file_path.suffix,
        )
        if specular_file_path.is_file():
            specular_image = bpy.data.images.get(specular_file_path.name)
            if specular_image is None:
                specular_image = bpy.data.images.load(specular_file_path.as_posix())

            specular_image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
            specular_image_node.image = specular_image

            if has_alpha:
                material.node_tree.links.new(specular_image_node.outputs[0], principled_bsdf.inputs[4])
                material.blend_method = 'HASHED'
            else:
                material.node_tree.links.new(specular_image_node.outputs[0], principled_bsdf.inputs[12])

    return material


def import_shader(
    logger: logging.Logger,
    game_type: utils.GameType,
    endianness: str,
    shader_id: int,
    shader_file_path_id_map: dict[int, pathlib.Path],
    texture_file_path_id_map: dict[int, pathlib.Path],
) -> bpy.types.Material | None:
    """Import a shader and create a Blender material for it."""
    shader_file_path = shader_file_path_id_map.get(shader_id)

    material = None

    if shader_file_path is not None:
        shader_desc = None
        try:
            shader_desc = shader.read_file(shader_file_path, game_type, endianness)
        except utils.FileReadError as _:
            logger.info(f"Could not import shader {shader_file_path}")  # noqa: G004

        if type(shader_desc) is shader.ShaderIDs:
            shader_file_path = shader_file_path_id_map.get(shader_desc.ids[-1])

            if shader_file_path is not None:
                try:
                    shader_desc = shader.read_file(shader_file_path, game_type, endianness)
                except utils.FileReadError as _:
                    shader_desc = None
                    logger.info(f"Could not import shader {shader_file_path}")  # noqa: G004
            else:
                shader_desc = None

        if shader_desc is not None and shader_desc.render_passes:
            render_pass = shader_desc.render_passes[0]

            match game_type:
                case utils.GameType.THESIMS | utils.GameType.THESIMSBUSTINOUT:
                    has_alpha = render_pass.flags & 0x4 != 0
                case (
                    utils.GameType.THEURBZ
                    | utils.GameType.THESIMS2
                    | utils.GameType.THESIMS2PETS
                    | utils.GameType.THESIMS2CASTAWAY
                ):
                    has_alpha = render_pass.raster_modes & 0x40 != 0 or render_pass.flags & 0x4 != 0
                case _:
                    has_alpha = False

            texture_file_path = texture_file_path_id_map.get(render_pass.texture_id)

            if texture_file_path:
                material = create_material(
                    shader_file_path.stem,
                    texture_file_path,
                    has_alpha=has_alpha,
                )

    return material
