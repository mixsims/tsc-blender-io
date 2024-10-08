"""Read animation files."""

import ctypes
import dataclasses
import math
import mathutils
import pathlib
import struct
import typing


from . import bit_array
from . import utils


@dataclasses.dataclass
class QuaternionKeyframe:
    """Quaternion Keyframe."""

    frame: int
    bias: float
    rotation: mathutils.Quaternion


def decompress_quaternion_keyframes(
    stream_data: bit_array.BitArray,
    index: int,
    fps: float,
    game_type: utils.GameType,
) -> list[QuaternionKeyframe]:
    """Decompress quaternion keyframes."""
    index = -index

    keyframe_count = stream_data.get_bits_unsigned(index, 20)
    index += 20

    delta_time_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_scale = 0.0 if bias_bit_count == 0 else stream_data.signed_bits_to_float_scaler(bias_bit_count)

    quaternion_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    quaternion_scale = stream_data.signed_bits_to_float_scaler(quaternion_bit_count)

    frame_count_multiplier = 1 if fps == 60.0 else 2

    frame_count = 0
    keyframes = []

    for _ in range(keyframe_count):
        delta_time = stream_data.get_bits_unsigned(index, delta_time_bit_count)
        index += delta_time_bit_count

        bias = bias_scale * float(stream_data.get_bits_signed(index, bias_bit_count)) if bias_bit_count > 0 else 0.0
        index += bias_bit_count

        if game_type in (utils.GameType.THESIMS2PETS, utils.GameType.THESIMS2CASTAWAY, utils.GameType.THESIMS3):
            # skip unknown bit
            index += 1

            quat = [0.0, 0.0, 0.0, 0.0]
            for i in range(3):
                quat[i] = quaternion_scale * stream_data.get_bits_signed(index, quaternion_bit_count)
                index += quaternion_bit_count

            quat[3] = 1.0 - ((quat[1] * quat[1]) + (quat[2] * quat[2]) + (quat[3] * quat[3]))

            negate_x = stream_data.get_bit(index)
            index += 1

            if quat[3] > 0.0:
                quat[3] = math.sqrt(quat[3])

                if negate_x:
                    quat[3] = -quat[3]
            else:
                quat[3] = 0.0

            quat = [quat[3], quat[0], quat[1], quat[2]]

        else:
            quat = [0.0, 0.0, 0.0, 0.0]
            for i in range(1, 4):
                quat[i] = quaternion_scale * stream_data.get_bits_signed(index, quaternion_bit_count)
                index += quaternion_bit_count

            quat[0] = 1.0 - ((quat[1] * quat[1]) + (quat[2] * quat[2]) + (quat[3] * quat[3]))

            negate_x = stream_data.get_bit(index)
            index += 1

            if quat[0] > 0.0:
                quat[0] = math.sqrt(quat[0])

                if negate_x:
                    quat[0] = -quat[0]
            else:
                quat[0] = 0.0

            quat = [quat[3], quat[0], quat[1], quat[2]]

        frame_count += delta_time + 1

        keyframes.append(
            QuaternionKeyframe(
                (frame_count * frame_count_multiplier) - 1,
                bias,
                mathutils.Quaternion(quat).normalized(),
            ),
        )

    return keyframes


def decompress_quaternion_1_dof_keyframes(
    stream_data: bit_array.BitArray,
    index: int,
    fps: float,
) -> list[QuaternionKeyframe]:
    """Decompress quaternion 1 dof keyframes."""
    index = -index

    x = stream_data.get_float(index)
    index += 32

    y = stream_data.get_float(index)
    index += 32

    z = stream_data.get_float(index)
    index += 32

    keyframe_count = stream_data.get_bits_unsigned(index, 20)
    index += 20

    delta_time_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_scale = 0.0 if bias_bit_count == 0 else stream_data.signed_bits_to_float_scaler(bias_bit_count)

    element_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    if element_bit_count == 0:
        element_bit_count = 32

    if element_bit_count == 32:
        element_scale = 1.0
        element_offset = 0.0
    else:
        element_scale = stream_data.unsigned_bits_to_float_scaler(element_bit_count)

        scale_float = stream_data.get_float(index)
        index += 32

        element_scale = scale_float * element_scale

        element_offset = stream_data.get_float(index)
        index += 32

    frame_count_multiplier = 1 if fps == 60.0 else 2

    frame_count = 0
    keyframes = []

    for _ in range(keyframe_count):
        delta_time = stream_data.get_bits_unsigned(index, delta_time_bit_count)
        index += delta_time_bit_count

        bias = bias_scale * float(stream_data.get_bits_signed(index, bias_bit_count))
        index += bias_bit_count

        if element_bit_count == 32:
            element = stream_data.get_float(index)
            index += 32
        else:
            element = element_offset + (element_scale * stream_data.get_bits_unsigned(index, element_bit_count))
            index += element_bit_count

        sin = math.sin(0.5 * element)
        w = math.cos(0.5 * element)

        frame_count += delta_time + 1

        keyframes.append(
            QuaternionKeyframe(
                (frame_count * frame_count_multiplier) - 1,
                bias,
                mathutils.Quaternion((w, x * sin, y * sin, z * sin)).normalized(),
            ),
        )

    return keyframes


@dataclasses.dataclass
class VectorKeyframe:
    """Vector Keyframe."""

    frame: int
    bias: float
    vector: mathutils.Vector


def decompress_vector_keyframes(
    stream_data: bit_array.BitArray,
    index: int,
    fps: float,
    game_type: utils.GameType,
) -> list[VectorKeyframe]:
    """Decompress vector keyframes."""
    index = -index

    keyframe_count = stream_data.get_bits_unsigned(index, 20)
    index += 20

    delta_time_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    bias_scale = 0.0 if bias_bit_count == 0 else stream_data.signed_bits_to_float_scaler(bias_bit_count)

    vector_bit_count = stream_data.get_bits_unsigned(index, 5)
    index += 5

    vector_scale = 1.0 if vector_bit_count == 32 else stream_data.unsigned_bits_to_float_scaler(vector_bit_count)

    scale = [0.0, 0.0, 0.0]
    offset = [0.0, 0.0, 0.0]
    for i in range(3):
        scale[i] = vector_scale * stream_data.get_float(index)
        index += 32

        offset[i] = stream_data.get_float(index)
        index += 32

    frame_count_multiplier = 1 if fps == 60.0 else 2

    frame_count = 0
    keyframes = []

    for _ in range(keyframe_count):
        delta_time = stream_data.get_bits_unsigned(index, delta_time_bit_count)
        index += delta_time_bit_count

        bias = bias_scale * float(stream_data.get_bits_unsigned(index, bias_bit_count)) if bias_bit_count > 0 else 0.0
        index += bias_bit_count

        if game_type in (utils.GameType.THESIMS2PETS, utils.GameType.THESIMS2CASTAWAY, utils.GameType.THESIMS3):
            # skip unknown bit
            index += 1

        vector = [0.0, 0.0, 0.0]
        for i in range(3):
            if vector_bit_count == 32:
                value = stream_data.get_float(index)
            else:
                value = stream_data.get_bits_unsigned(index, vector_bit_count)
            index += vector_bit_count

            value = float(value & 1 | value >> 2) if ctypes.c_int32(value).value < 0 else float(value)

            vector[i] = (value * scale[i]) + offset[i]

        frame_count += delta_time + 1

        keyframes.append(VectorKeyframe((frame_count * frame_count_multiplier) - 1, bias, mathutils.Vector(vector)))

    return keyframes


@dataclasses.dataclass
class Bone:
    """Bone."""

    rotation_keyframes: list[QuaternionKeyframe]
    scale_keyframes: list[int]
    location_keyframes: list[int]


def read_bone(
    file: typing.BinaryIO,
    endianness: str,
    game_type: utils.GameType,
    static_data: list[float],
    stream_data: bit_array.BitArray,
    fps: float,
) -> Bone:
    """Read bone."""
    rotation_index = struct.unpack(endianness + 'i', file.read(4))[0]
    scale_index = struct.unpack(endianness + 'i', file.read(4))[0]
    location_index = struct.unpack(endianness + 'i', file.read(4))[0]

    match game_type:
        case utils.GameType.THESIMSBUSTINOUT:
            file.read(16)
        case (
            utils.GameType.THEURBZ
            | utils.GameType.THESIMS2
            | utils.GameType.THESIMS2PETS
            | utils.GameType.THESIMS2CASTAWAY
            | utils.GameType.THESIMS3
        ):
            file.read(20)

    rotation_keyframes = []
    scale_keyframes = []
    location_keyframes = []

    if rotation_index > 0:
        rotation_keyframes = [
            QuaternionKeyframe(
                0,
                1.0,
                mathutils.Quaternion(
                    (
                        static_data[rotation_index + 3],
                        static_data[rotation_index],
                        static_data[rotation_index + 1],
                        static_data[rotation_index + 2],
                    ),
                ),
            ),
        ]
    elif rotation_index < 0:
        is_1_dof = False

        if game_type in (utils.GameType.THESIMS2PETS, utils.GameType.THESIMS2CASTAWAY, utils.GameType.THESIMS3):
            is_1_dof = stream_data.get_bit(-rotation_index)
            rotation_index -= 1

        if is_1_dof:
            rotation_keyframes = decompress_quaternion_1_dof_keyframes(stream_data, rotation_index, fps)
        else:
            rotation_keyframes = decompress_quaternion_keyframes(stream_data, rotation_index, fps, game_type)

    else:
        rotation_keyframes = [QuaternionKeyframe(0, 1.0, mathutils.Quaternion((1.0, 0.0, 0.0, 0.0)))]

    if scale_index > 0:
        scale_keyframes = [
            VectorKeyframe(
                0,
                1.0,
                mathutils.Vector(static_data[scale_index : scale_index + 3]),
            ),
        ]
    elif scale_index < 0:
        scale_keyframes = decompress_vector_keyframes(stream_data, scale_index, fps, game_type)
    else:
        scale_keyframes = [VectorKeyframe(0, 1.0, mathutils.Vector((1.0, 1.0, 1.0)))]

    if location_index > 0:
        location_keyframes = [
            VectorKeyframe(
                0,
                1.0,
                mathutils.Vector(static_data[location_index : location_index + 3]),
            ),
        ]
    elif location_index < 0:
        location_keyframes = decompress_vector_keyframes(stream_data, location_index, fps, game_type)
    else:
        location_keyframes = [VectorKeyframe(0, 1.0, mathutils.Vector((0.0, 0.0, 0.0)))]

    return Bone(rotation_keyframes, scale_keyframes, location_keyframes)


@dataclasses.dataclass
class Animation:
    """Animation."""

    name: str
    frame_count: int
    bones: list[Bone]
    intensity: float
    flags: int
    blend_type: int
    blend_m1: float
    blend_m2: float
    blend_duration: float
    blend_speed: float
    rotation_accumulator: int
    end_action: int


def read_animation(file: typing.BinaryIO, endianness: str, game_type: utils.GameType) -> Animation:
    """Read animation."""
    match game_type:
        case utils.GameType.THEURBZ:
            file.read(20)
        case (
            utils.GameType.THESIMS2
            | utils.GameType.THESIMS2PETS
            | utils.GameType.THESIMS2CASTAWAY
            | utils.GameType.THESIMS3
        ):
            file.read(16)

    name = utils.read_null_terminated_string(file)

    match game_type:
        case (
            utils.GameType.THESIMS2
            | utils.GameType.THESIMS2PETS
            | utils.GameType.THESIMS2CASTAWAY
            | utils.GameType.THESIMS3
        ):
            file.read(4)

    frame_count = struct.unpack(endianness + 'I', file.read(4))[0]

    file.read(12)
    file.read(12)

    bone_count = struct.unpack(endianness + 'I', file.read(4))[0]
    bone_position = file.tell()

    match game_type:
        case utils.GameType.THESIMS:
            bone_size = 12
        case utils.GameType.THESIMSBUSTINOUT:
            bone_size = 28
        case (
            utils.GameType.THEURBZ
            | utils.GameType.THESIMS2
            | utils.GameType.THESIMS2PETS
            | utils.GameType.THESIMS2CASTAWAY
            | utils.GameType.THESIMS3
        ):
            bone_size = 32
        case _:
            raise utils.FileReadError

    file.seek(bone_position + (bone_count * bone_size) + 4)

    if game_type in (utils.GameType.THESIMS2PETS, utils.GameType.THESIMS2CASTAWAY, utils.GameType.THESIMS3):
        file.read(4)

    static_float_count = struct.unpack(endianness + 'I', file.read(4))[0]
    static_data = [struct.unpack(endianness + 'f', file.read(4))[0] for _ in range(static_float_count)]

    stream_data_bit_count = struct.unpack(endianness + 'I', file.read(4))[0]

    stream_data_length = ((stream_data_bit_count + 0x1F) >> 5) << 2

    stream_data = [struct.unpack(endianness + 'I', file.read(4))[0] for _ in range(int(stream_data_length / 4))]

    stream_data = bit_array.BitArray(stream_data)

    fps = struct.unpack(endianness + 'f', file.read(4))[0]
    intensity = struct.unpack(endianness + 'f', file.read(4))[0]
    flags = struct.unpack(endianness + 'I', file.read(4))[0]
    blend_type = struct.unpack(endianness + 'B', file.read(1))[0]
    blend_m1 = struct.unpack(endianness + 'f', file.read(4))[0]
    blend_m2 = struct.unpack(endianness + 'f', file.read(4))[0]
    blend_duration = struct.unpack(endianness + 'f', file.read(4))[0]
    blend_speed = struct.unpack(endianness + 'f', file.read(4))[0]
    rot_accum = struct.unpack(endianness + 'B', file.read(1))[0]
    end_action = struct.unpack(endianness + 'B', file.read(1))[0]

    end_position = file.tell()

    file.seek(bone_position)

    bones = [read_bone(file, endianness, game_type, static_data, stream_data, fps) for _ in range(bone_count)]

    file.seek(end_position)

    if game_type in (utils.GameType.THESIMS2, utils.GameType.THESIMS2PETS, utils.GameType.THESIMS2CASTAWAY):
        sound_count = struct.unpack(endianness + 'I', file.read(4))[0]

        for _ in range(sound_count):
            file.read(8)
            _ = utils.read_null_terminated_string(file)

    if game_type == utils.GameType.THESIMS3:
        file.read(4)

    if len(file.read(4)) != 4:
        raise utils.FileReadError

    frame_count = frame_count if fps == 60.0 else frame_count * 2

    return Animation(
        name,
        frame_count,
        bones,
        intensity,
        flags,
        blend_type,
        blend_m1,
        blend_m2,
        blend_duration,
        blend_speed,
        rot_accum,
        end_action,
    )


def read_file(file_path: pathlib.Path, game_type: utils.GameType, endianness: str) -> Animation:
    """Read an animation file."""
    try:
        with file_path.open(mode='rb') as file:
            animation = read_animation(file, endianness, game_type)

            if len(file.read(1)) != 0:
                raise utils.FileReadError

            return animation

    except (OSError, IndexError, ValueError, ZeroDivisionError, struct.error) as exception:
        raise utils.FileReadError from exception
