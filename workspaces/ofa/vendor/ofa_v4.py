#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ofa.py（V4）
===========

Windows / CUDA 下使用 ctypes 直接调用 NVIDIA Optical Flow SDK 5.0 / C API 5.0。

设计目标
--------
- 不依赖 OpenCV、Visual Studio 或自行编译的扩展。
- 从 NVIDIA 显卡驱动加载 nvofapi64.dll。
- 使用 PyTorch 已经建立的 CUDA Context 和当前 CUDA Stream。
- 输入采用官方支持的 GRAYSCALE8 CUDA 缓冲区：
      torch.uint8, shape=(H, W), device="cuda"
- 输出保留官方 SHORT2 / S10.5 原始格式：
      raw_flow: torch.int16, shape=(ceil(H/grid), ceil(W/grid), 2)
  同时在 GPU 上转换为像素单位：
      flow: torch.float32, 同样形状，raw_flow / 32
- 可选输出官方推荐的 UINT8 cost：
      cost: torch.uint8，数值越大通常代表对应光流越不可靠。

方向
----
execute(input_frame, reference_frame) 返回 input_frame -> reference_frame 的光流。
例如物体从上一帧向右移动 12 像素，预期 dx 约为 +12。

依据
----
NVIDIA Optical Flow SDK 官方头文件：
- nvOpticalFlowCommon.h
- nvOpticalFlowCuda.h

NVIDIA NVOFA Programming Guide：
https://docs.nvidia.com/video-technologies/optical-flow-sdk/nvofa-programming-guide/index.html

注意
----
本脚本按 NVIDIA Optical Flow SDK 5.0 的 C API 5.0 头文件映射 ctypes 结构。
它必须在 Windows、支持 NVOFA 的 NVIDIA GPU 和正常 NVIDIA 驱动下运行。
"""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# NVIDIA Optical Flow SDK 5.0 / C API 5.0 constants
# ---------------------------------------------------------------------------

NV_OF_API_MAJOR_VERSION = 5
NV_OF_API_MINOR_VERSION = 0
NV_OF_API_VERSION = (
    (NV_OF_API_MAJOR_VERSION << 4) | NV_OF_API_MINOR_VERSION
)

MAX_NUM_PLANES = 3


class NV_OF_STATUS:
    SUCCESS = 0
    ERR_OF_NOT_AVAILABLE = 1
    ERR_UNSUPPORTED_DEVICE = 2
    ERR_DEVICE_DOES_NOT_EXIST = 3
    ERR_INVALID_PTR = 4
    ERR_INVALID_PARAM = 5
    ERR_INVALID_CALL = 6
    ERR_INVALID_VERSION = 7
    ERR_OUT_OF_MEMORY = 8
    ERR_NOT_INITIALIZED = 9
    ERR_UNSUPPORTED_FEATURE = 10
    ERR_GENERIC = 11

    _NAMES = {
        SUCCESS: "NV_OF_SUCCESS",
        ERR_OF_NOT_AVAILABLE: "NV_OF_ERR_OF_NOT_AVAILABLE",
        ERR_UNSUPPORTED_DEVICE: "NV_OF_ERR_UNSUPPORTED_DEVICE",
        ERR_DEVICE_DOES_NOT_EXIST: "NV_OF_ERR_DEVICE_DOES_NOT_EXIST",
        ERR_INVALID_PTR: "NV_OF_ERR_INVALID_PTR",
        ERR_INVALID_PARAM: "NV_OF_ERR_INVALID_PARAM",
        ERR_INVALID_CALL: "NV_OF_ERR_INVALID_CALL",
        ERR_INVALID_VERSION: "NV_OF_ERR_INVALID_VERSION",
        ERR_OUT_OF_MEMORY: "NV_OF_ERR_OUT_OF_MEMORY",
        ERR_NOT_INITIALIZED: "NV_OF_ERR_NOT_INITIALIZED",
        ERR_UNSUPPORTED_FEATURE: "NV_OF_ERR_UNSUPPORTED_FEATURE",
        ERR_GENERIC: "NV_OF_ERR_GENERIC",
    }

    @classmethod
    def name(cls, value: int) -> str:
        return cls._NAMES.get(int(value), f"NV_OF_STATUS({value})")


class NV_OF_CAPS:
    SUPPORTED_OUTPUT_GRID_SIZES = 0
    SUPPORTED_HINT_GRID_SIZES = 1
    SUPPORT_HINT_WITH_OF_MODE = 2
    SUPPORT_HINT_WITH_ST_MODE = 3
    WIDTH_MIN = 4
    HEIGHT_MIN = 5
    WIDTH_MAX = 6
    HEIGHT_MAX = 7
    SUPPORT_ROI = 8
    SUPPORT_ROI_MAX_NUM = 9
    SUPPORT_STEREO = 10


class NV_OF_PERF_LEVEL:
    SLOW = 5
    MEDIUM = 10
    FAST = 20


class NV_OF_OUTPUT_VECTOR_GRID_SIZE:
    GRID_1 = 1
    GRID_2 = 2
    GRID_4 = 4


class NV_OF_HINT_VECTOR_GRID_SIZE:
    UNDEFINED = 0


class NV_OF_MODE:
    OPTICALFLOW = 1


class NV_OF_BUFFER_USAGE:
    INPUT = 1
    OUTPUT = 2
    HINT = 3
    COST = 4
    GLOBAL_FLOW = 5


class NV_OF_BUFFER_FORMAT:
    GRAYSCALE8 = 1
    NV12 = 2
    ABGR8 = 3
    SHORT = 4
    SHORT2 = 5
    UINT = 6
    UINT8 = 7


class NV_OF_STEREO_DISPARITY_RANGE:
    UNDEFINED = 0


class NV_OF_PRED_DIRECTION:
    FORWARD = 0
    BOTH = 2


class NV_OF_CUDA_BUFFER_TYPE:
    CUARRAY = 1
    CUDEVICEPTR = 2


# CUDA Driver API constants.
CU_MEMORYTYPE_HOST = 1
CU_MEMORYTYPE_DEVICE = 2
CU_MEMORYTYPE_ARRAY = 3
CU_MEMORYTYPE_UNIFIED = 4


# ---------------------------------------------------------------------------
# ctypes structures: official headers use 1-byte packing for common structures.
# ---------------------------------------------------------------------------

class NV_OF_INIT_PARAMS(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("outGridSize", ctypes.c_int),
        ("hintGridSize", ctypes.c_int),
        ("mode", ctypes.c_int),
        ("perfLevel", ctypes.c_int),
        ("enableExternalHints", ctypes.c_int),
        ("enableOutputCost", ctypes.c_int),
        ("hPrivData", ctypes.c_void_p),
        ("disparityRange", ctypes.c_int),
        ("enableRoi", ctypes.c_int),
        ("predDirection", ctypes.c_int),
        ("enableGlobalFlow", ctypes.c_int),
        ("inputBufferFormat", ctypes.c_int),
    ]


class NV_OF_BUFFER_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("bufferUsage", ctypes.c_int),
        ("bufferFormat", ctypes.c_int),
    ]


class NV_OF_ROI_RECT(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("start_x", ctypes.c_uint32),
        ("start_y", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
    ]


class NV_OF_EXECUTE_INPUT_PARAMS(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("inputFrame", ctypes.c_void_p),
        ("referenceFrame", ctypes.c_void_p),
        ("externalHints", ctypes.c_void_p),
        ("disableTemporalHints", ctypes.c_int),
        ("padding", ctypes.c_uint32),
        ("hPrivData", ctypes.c_void_p),
        ("padding2", ctypes.c_uint32),
        ("numRois", ctypes.c_uint32),
        ("roiData", ctypes.POINTER(NV_OF_ROI_RECT)),
    ]


class NV_OF_EXECUTE_OUTPUT_PARAMS(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("outputBuffer", ctypes.c_void_p),
        ("outputCostBuffer", ctypes.c_void_p),
        ("hPrivData", ctypes.c_void_p),
        ("bwdOutputBuffer", ctypes.c_void_p),
        ("bwdOutputCostBuffer", ctypes.c_void_p),
        ("globalFlowBuffer", ctypes.c_void_p),
    ]


class NV_OF_BUFFER_STRIDE(ctypes.Structure):
    _fields_ = [
        ("strideXInBytes", ctypes.c_uint32),
        ("strideYInBytes", ctypes.c_uint32),
    ]


class NV_OF_CUDA_BUFFER_STRIDE_INFO(ctypes.Structure):
    _fields_ = [
        ("strideInfo", NV_OF_BUFFER_STRIDE * MAX_NUM_PLANES),
        ("numPlanes", ctypes.c_uint32),
    ]


class CUDA_MEMCPY2D(ctypes.Structure):
    """
    CUDA Driver API 的 CUDA_MEMCPY2D。

    本脚本只使用 device -> device 复制，但保留官方完整字段顺序，
    以便正确调用 cuMemcpy2DAsync_v2。
    """
    _fields_ = [
        ("srcXInBytes", ctypes.c_size_t),
        ("srcY", ctypes.c_size_t),
        ("srcMemoryType", ctypes.c_int),
        ("srcHost", ctypes.c_void_p),
        ("srcDevice", ctypes.c_uint64),
        ("srcArray", ctypes.c_void_p),
        ("srcPitch", ctypes.c_size_t),
        ("dstXInBytes", ctypes.c_size_t),
        ("dstY", ctypes.c_size_t),
        ("dstMemoryType", ctypes.c_int),
        ("dstHost", ctypes.c_void_p),
        ("dstDevice", ctypes.c_uint64),
        ("dstArray", ctypes.c_void_p),
        ("dstPitch", ctypes.c_size_t),
        ("WidthInBytes", ctypes.c_size_t),
        ("Height", ctypes.c_size_t),
    ]


# Windows NVOFAPI is __stdcall. On non-Windows this fallback keeps the module
# importable for syntax inspection, though the class deliberately rejects use.
_CALL = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)

PFNNVCREATEOPTICALFLOWCUDA = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
)
PFNNVOFINIT = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(NV_OF_INIT_PARAMS),
)
PFNNVOFCREATEGPUBUFFERCUDA = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(NV_OF_BUFFER_DESCRIPTOR),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_void_p),
)
PFNNVOFGPUBUFFERGETCUARRAY = _CALL(
    ctypes.c_void_p,
    ctypes.c_void_p,
)
PFNNVOFGPUBUFFERGETCUDEVICEPTR = _CALL(
    ctypes.c_uint64,
    ctypes.c_void_p,
)
PFNVOFGPUBUFFERGETSTRIDEINFO = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(NV_OF_CUDA_BUFFER_STRIDE_INFO),
)
PFNNVOFSETIOCUDASTREAMS = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
)
PFNNVOFEXECUTE = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(NV_OF_EXECUTE_INPUT_PARAMS),
    ctypes.POINTER(NV_OF_EXECUTE_OUTPUT_PARAMS),
)
PFNNVOFDESTROYGPUBUFFERCUDA = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
)
PFNNVOFDESTROY = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
)
PFNNVOFGETLASTERROR = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_char),
    ctypes.POINTER(ctypes.c_uint32),
)
PFNNVOFGETCAPS = _CALL(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
)


class NV_OF_CUDA_API_FUNCTION_LIST(ctypes.Structure):
    _fields_ = [
        ("nvCreateOpticalFlowCuda", PFNNVCREATEOPTICALFLOWCUDA),
        ("nvOFInit", PFNNVOFINIT),
        ("nvOFCreateGPUBufferCuda", PFNNVOFCREATEGPUBUFFERCUDA),
        ("nvOFGPUBufferGetCUarray", PFNNVOFGPUBUFFERGETCUARRAY),
        ("nvOFGPUBufferGetCUdeviceptr", PFNNVOFGPUBUFFERGETCUDEVICEPTR),
        ("nvOFGPUBufferGetStrideInfo", PFNVOFGPUBUFFERGETSTRIDEINFO),
        ("nvOFSetIOCudaStreams", PFNNVOFSETIOCUDASTREAMS),
        ("nvOFExecute", PFNNVOFEXECUTE),
        ("nvOFDestroyGPUBufferCuda", PFNNVOFDESTROYGPUBUFFERCUDA),
        ("nvOFDestroy", PFNNVOFDESTROY),
        ("nvOFGetLastError", PFNNVOFGETLASTERROR),
        ("nvOFGetCaps", PFNNVOFGETCAPS),
    ]


@dataclass(frozen=True)
class OFAResult:
    """NVOF 单次执行结果。

    所有 Tensor 都位于 CUDA 上，并由引擎的环形槽位复用。调用者应当在
    ``buffer_count`` 次后续 execute() 之前消费结果；需要长期保存时传入
    ``copy_result=True``。

    raw_flow:
        官方 SHORT2 / S10.5 输出，shape=(grid_h, grid_w, 2)，int16。
    flow:
        可选的像素单位 float32 光流，等于 raw_flow / 32。
    cost:
        可选 UINT8 cost，数值越大通常表示向量越不可靠。
    """
    raw_flow: torch.Tensor
    flow: Optional[torch.Tensor]
    cost: Optional[torch.Tensor]
    grid_size: int
    input_width: int
    input_height: int
    slot_index: int


@dataclass
class _OFABuffer:
    handle: ctypes.c_void_p
    device_ptr: int
    pitch_bytes: int
    width: int
    height: int
    bytes_per_pixel: int


@dataclass(frozen=True)
class OffsetResult:
    offset: torch.Tensor
    dispersion: torch.Tensor
    valid_ratio: torch.Tensor
    inlier_ratio: torch.Tensor
    peak_ratio: torch.Tensor
    confidence: torch.Tensor
    cost_mean: torch.Tensor
    fb_valid_ratio: torch.Tensor


@dataclass
class _OFASlot:
    input_a: _OFABuffer
    input_b: _OFABuffer
    output: _OFABuffer
    cost_buffer: Optional[_OFABuffer]
    backward_output: Optional[_OFABuffer]
    backward_cost_buffer: Optional[_OFABuffer]
    raw_flow: torch.Tensor
    flow: torch.Tensor
    cost_tensor: Optional[torch.Tensor]
    backward_raw_flow: Optional[torch.Tensor]
    backward_flow: Optional[torch.Tensor]
    backward_cost_tensor: Optional[torch.Tensor]
    ready_event: torch.cuda.Event
    in_use: bool


class NVOFError(RuntimeError):
    pass


def _load_system_dll(name: str) -> ctypes.WinDLL:
    """优先从 System32 加载驱动 DLL，避免工作目录同名 DLL 劫持。"""
    load_library_search_system32 = 0x00000800
    try:
        return ctypes.WinDLL(name, winmode=load_library_search_system32)
    except (TypeError, OSError):
        return ctypes.WinDLL(name)


def _resolve_cuda_symbol(lib: ctypes.WinDLL, *names: str):
    for name in names:
        try:
            return getattr(lib, name)
        except AttributeError:
            continue
    raise NVOFError(f"nvcuda.dll 中未找到 CUDA 函数：{', '.join(names)}")


class NvidiaOpticalFlowCuda:
    """NVIDIA NVOFA CUDA 后端的低层、预分配 Python 包装。

    性能设计
    --------
    - NVOF 会话只创建和初始化一次。
    - 输入、输出、cost 和 PyTorch Tensor 全部预分配。
    - 默认建立独立 input/output CUDA Stream，并且仅设置一次 NVOF Stream。
    - 默认使用 4 个环形槽位，避免连续提交时立即覆盖上一组缓冲区。
    - execute() 不进行 CPU 同步；结果通过 CUDA Stream 依赖返回。

    Parameters
    ----------
    width, height:
        固定输入尺寸。改变分辨率时重新创建实例。
    gpu_id:
        PyTorch CUDA 设备编号。
    grid_size:
        官方输出网格尺寸，通常为 4；会通过 nvOFGetCaps 验证。
    preset:
        ``slow``、``medium`` 或 ``fast``；V4 默认 ``medium``。
    enable_cost:
        是否启用 UINT8 cost 输出。
    bidirectional:
        为 True 时使用 SDK 5.0 的单次 Execute 同时输出前向和后向光流。
    buffer_count:
        输入/参考帧“成对槽位”的数量；每个槽位包含 2 个输入缓冲区。
        默认 4 个槽位即 8 个输入缓冲区，用于连续提交和低分辨率测试。
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        gpu_id: int = 0,
        grid_size: int = 4,
        preset: str = "medium",
        enable_cost: bool = True,
        buffer_count: int = 4,
        bidirectional: bool = True,
    ) -> None:
        if os.name != "nt":
            raise OSError("此版本 ofa.py 面向原生 Windows；当前系统不是 Windows。")
        if width <= 0 or height <= 0:
            raise ValueError("width 和 height 必须为正数。")
        if grid_size not in (1, 2, 4):
            raise ValueError("grid_size 只能是 1、2 或 4。")
        if buffer_count < 2:
            raise ValueError("buffer_count 至少为 2，推荐 4～6。")
        if not torch.cuda.is_available():
            raise NVOFError("PyTorch 未检测到可用 CUDA 设备。")

        self.width = int(width)
        self.height = int(height)
        self.gpu_id = int(gpu_id)
        self.device = torch.device(f"cuda:{self.gpu_id}")
        self.grid_size = int(grid_size)
        self.out_width = (self.width + self.grid_size - 1) // self.grid_size
        self.out_height = (self.height + self.grid_size - 1) // self.grid_size
        self.enable_cost = bool(enable_cost)
        self.buffer_count = int(buffer_count)
        self.bidirectional = bool(bidirectional)
        self.driver_api_version = 0
        self._closed = False
        self._buffers: list[_OFABuffer] = []
        self._slots: list[_OFASlot] = []
        self._next_slot = 0
        self.h_of = ctypes.c_void_p()

        preset_map = {
            "slow": NV_OF_PERF_LEVEL.SLOW,
            "medium": NV_OF_PERF_LEVEL.MEDIUM,
            "fast": NV_OF_PERF_LEVEL.FAST,
        }
        self.preset = preset.lower()
        try:
            self.perf_level = preset_map[self.preset]
        except KeyError as exc:
            raise ValueError("preset 必须是 slow、medium 或 fast。") from exc

        # 建立并固定 PyTorch primary CUDA context。
        torch.cuda.set_device(self.device)
        torch.empty(1, device=self.device)
        torch.cuda.current_stream(self.device)

        # 独立输入/输出 Stream：NVOF API 负责在两条 Stream 间建立依赖。
        self.input_stream = torch.cuda.Stream(device=self.device)
        self.output_stream = torch.cuda.Stream(device=self.device)

        self.nvof = _load_system_dll("nvofapi64.dll")
        self.cuda = _load_system_dll("nvcuda.dll")
        self._configure_cuda_driver()

        self.api = NV_OF_CUDA_API_FUNCTION_LIST()
        self._configure_nvof_entry()

        try:
            self._create_session()
            self._validate_caps()
            self._set_streams_once()
            self._initialize_session()
            self._create_slots()
        except BaseException:
            self.close()
            raise

    # ----------------------------- initialization -------------------------

    def _configure_cuda_driver(self) -> None:
        self.cuda.cuInit.argtypes = [ctypes.c_uint]
        self.cuda.cuInit.restype = ctypes.c_int

        self.cuda.cuCtxGetCurrent.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.cuda.cuCtxGetCurrent.restype = ctypes.c_int

        self._cu_memcpy_2d_async = _resolve_cuda_symbol(
            self.cuda, "cuMemcpy2DAsync_v2", "cuMemcpy2DAsync"
        )
        self._cu_memcpy_2d_async.argtypes = [
            ctypes.POINTER(CUDA_MEMCPY2D),
            ctypes.c_void_p,
        ]
        self._cu_memcpy_2d_async.restype = ctypes.c_int

        self.cuda.cuGetErrorString.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        self.cuda.cuGetErrorString.restype = ctypes.c_int
        self._check_cuda(self.cuda.cuInit(0), "cuInit")

    def _configure_nvof_entry(self) -> None:
        self.nvof.NvOFAPICreateInstanceCuda.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(NV_OF_CUDA_API_FUNCTION_LIST),
        ]
        self.nvof.NvOFAPICreateInstanceCuda.restype = ctypes.c_int

        try:
            get_max_version = self.nvof.NvOFGetMaxSupportedApiVersion
        except AttributeError:
            get_max_version = None
        if get_max_version is not None:
            get_max_version.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
            get_max_version.restype = ctypes.c_int
            max_version = ctypes.c_uint32()
            status = get_max_version(ctypes.byref(max_version))
            if status == NV_OF_STATUS.SUCCESS:
                self.driver_api_version = int(max_version.value)
                if max_version.value < NV_OF_API_VERSION:
                    raise NVOFError(
                        "显卡驱动支持的 NVOF API 版本过低："
                        f"0x{max_version.value:X} < 0x{NV_OF_API_VERSION:X}"
                    )

        status = self.nvof.NvOFAPICreateInstanceCuda(
            NV_OF_API_VERSION, ctypes.byref(self.api)
        )
        self._check_of(status, "NvOFAPICreateInstanceCuda", allow_no_handle=True)

    def _create_session(self) -> None:
        context = ctypes.c_void_p()
        self._check_cuda(
            self.cuda.cuCtxGetCurrent(ctypes.byref(context)), "cuCtxGetCurrent"
        )
        if not context.value:
            raise NVOFError("当前线程没有 CUDA Context；PyTorch CUDA 初始化异常。")
        status = self.api.nvCreateOpticalFlowCuda(context, ctypes.byref(self.h_of))
        self._check_of(status, "nvCreateOpticalFlowCuda")
        if not self.h_of.value:
            raise NVOFError("nvCreateOpticalFlowCuda 返回了空句柄。")

    def _get_caps(self, cap: int) -> list[int]:
        size = ctypes.c_uint32(0)
        status = self.api.nvOFGetCaps(self.h_of, cap, None, ctypes.byref(size))
        self._check_of(status, f"nvOFGetCaps({cap})/size")
        if size.value == 0:
            return []
        values = (ctypes.c_uint32 * size.value)()
        status = self.api.nvOFGetCaps(
            self.h_of, cap, values, ctypes.byref(size)
        )
        self._check_of(status, f"nvOFGetCaps({cap})/values")
        return [int(values[i]) for i in range(size.value)]

    def _validate_caps(self) -> None:
        grids = self._get_caps(NV_OF_CAPS.SUPPORTED_OUTPUT_GRID_SIZES)
        if self.grid_size not in grids:
            raise NVOFError(
                f"请求 grid_size={self.grid_size}，显卡支持值为 {grids}。"
            )

        def one(cap: int) -> Optional[int]:
            values = self._get_caps(cap)
            return values[0] if values else None

        width_min = one(NV_OF_CAPS.WIDTH_MIN)
        height_min = one(NV_OF_CAPS.HEIGHT_MIN)
        width_max = one(NV_OF_CAPS.WIDTH_MAX)
        height_max = one(NV_OF_CAPS.HEIGHT_MAX)
        if width_min is not None and self.width < width_min:
            raise NVOFError(f"输入宽度低于 NVOF 最小值 {width_min}。")
        if height_min is not None and self.height < height_min:
            raise NVOFError(f"输入高度低于 NVOF 最小值 {height_min}。")
        if width_max is not None and self.width > width_max:
            raise NVOFError(f"输入宽度超过 NVOF 最大值 {width_max}。")
        if height_max is not None and self.height > height_max:
            raise NVOFError(f"输入高度超过 NVOF 最大值 {height_max}。")

    def _initialize_session(self) -> None:
        params = NV_OF_INIT_PARAMS()
        params.width = self.width
        params.height = self.height
        params.outGridSize = self.grid_size
        params.hintGridSize = NV_OF_HINT_VECTOR_GRID_SIZE.UNDEFINED
        params.mode = NV_OF_MODE.OPTICALFLOW
        params.perfLevel = self.perf_level
        params.enableExternalHints = 0
        params.enableOutputCost = int(self.enable_cost)
        params.hPrivData = None
        params.disparityRange = NV_OF_STEREO_DISPARITY_RANGE.UNDEFINED
        params.enableRoi = 0
        params.predDirection = (
            NV_OF_PRED_DIRECTION.BOTH
            if self.bidirectional
            else NV_OF_PRED_DIRECTION.FORWARD
        )
        params.enableGlobalFlow = 0
        params.inputBufferFormat = NV_OF_BUFFER_FORMAT.GRAYSCALE8
        self._check_of(self.api.nvOFInit(self.h_of, ctypes.byref(params)), "nvOFInit")

    def _set_streams_once(self) -> None:
        status = self.api.nvOFSetIOCudaStreams(
            self.h_of,
            ctypes.c_void_p(int(self.input_stream.cuda_stream)),
            ctypes.c_void_p(int(self.output_stream.cuda_stream)),
        )
        self._check_of(status, "nvOFSetIOCudaStreams")

    def _create_slots(self) -> None:
        for _ in range(self.buffer_count):
            input_a = self._create_buffer(
                NV_OF_BUFFER_USAGE.INPUT,
                NV_OF_BUFFER_FORMAT.GRAYSCALE8,
                self.width,
                self.height,
                1,
            )
            input_b = self._create_buffer(
                NV_OF_BUFFER_USAGE.INPUT,
                NV_OF_BUFFER_FORMAT.GRAYSCALE8,
                self.width,
                self.height,
                1,
            )
            output = self._create_buffer(
                NV_OF_BUFFER_USAGE.OUTPUT,
                NV_OF_BUFFER_FORMAT.SHORT2,
                self.out_width,
                self.out_height,
                4,
            )
            cost_buffer = (
                self._create_buffer(
                    NV_OF_BUFFER_USAGE.COST,
                    NV_OF_BUFFER_FORMAT.UINT8,
                    self.out_width,
                    self.out_height,
                    1,
                )
                if self.enable_cost
                else None
            )
            backward_output = (
                self._create_buffer(
                    NV_OF_BUFFER_USAGE.OUTPUT,
                    NV_OF_BUFFER_FORMAT.SHORT2,
                    self.out_width,
                    self.out_height,
                    4,
                )
                if self.bidirectional
                else None
            )
            backward_cost_buffer = (
                self._create_buffer(
                    NV_OF_BUFFER_USAGE.COST,
                    NV_OF_BUFFER_FORMAT.UINT8,
                    self.out_width,
                    self.out_height,
                    1,
                )
                if self.bidirectional and self.enable_cost
                else None
            )

            raw_flow = torch.empty(
                (self.out_height, self.out_width, 2),
                dtype=torch.int16,
                device=self.device,
            )
            flow = torch.empty_like(raw_flow, dtype=torch.float32)
            cost_tensor = (
                torch.empty(
                    (self.out_height, self.out_width),
                    dtype=torch.uint8,
                    device=self.device,
                )
                if self.enable_cost
                else None
            )
            backward_raw_flow = (
                torch.empty_like(raw_flow) if self.bidirectional else None
            )
            backward_flow = (
                torch.empty_like(flow) if self.bidirectional else None
            )
            backward_cost_tensor = (
                torch.empty_like(cost_tensor)
                if self.bidirectional and cost_tensor is not None
                else None
            )
            self._slots.append(
                _OFASlot(
                    input_a=input_a,
                    input_b=input_b,
                    output=output,
                    cost_buffer=cost_buffer,
                    backward_output=backward_output,
                    backward_cost_buffer=backward_cost_buffer,
                    raw_flow=raw_flow,
                    flow=flow,
                    cost_tensor=cost_tensor,
                    backward_raw_flow=backward_raw_flow,
                    backward_flow=backward_flow,
                    backward_cost_tensor=backward_cost_tensor,
                    ready_event=torch.cuda.Event(enable_timing=False, blocking=False),
                    in_use=False,
                )
            )

    def _create_buffer(
        self,
        usage: int,
        pixel_format: int,
        width: int,
        height: int,
        bytes_per_pixel: int,
    ) -> _OFABuffer:
        desc = NV_OF_BUFFER_DESCRIPTOR()
        desc.width = width
        desc.height = height
        desc.bufferUsage = usage
        desc.bufferFormat = pixel_format
        handle = ctypes.c_void_p()
        self._check_of(
            self.api.nvOFCreateGPUBufferCuda(
                self.h_of,
                ctypes.byref(desc),
                NV_OF_CUDA_BUFFER_TYPE.CUDEVICEPTR,
                ctypes.byref(handle),
            ),
            "nvOFCreateGPUBufferCuda",
        )
        if not handle.value:
            raise NVOFError("NVOF 创建了空 GPU Buffer 句柄。")
        device_ptr = int(self.api.nvOFGPUBufferGetCUdeviceptr(handle))
        if not device_ptr:
            self.api.nvOFDestroyGPUBufferCuda(handle)
            raise NVOFError("无法取得 NVOF GPU Buffer 的 CUdeviceptr。")
        stride_info = NV_OF_CUDA_BUFFER_STRIDE_INFO()
        self._check_of(
            self.api.nvOFGPUBufferGetStrideInfo(handle, ctypes.byref(stride_info)),
            "nvOFGPUBufferGetStrideInfo",
        )
        if stride_info.numPlanes < 1:
            self.api.nvOFDestroyGPUBufferCuda(handle)
            raise NVOFError("NVOF GPU Buffer 没有有效平面。")
        pitch = int(stride_info.strideInfo[0].strideXInBytes)
        minimum_pitch = int(width * bytes_per_pixel)
        if pitch < minimum_pitch:
            self.api.nvOFDestroyGPUBufferCuda(handle)
            raise NVOFError(
                f"NVOF Buffer pitch={pitch} 小于一行数据 {minimum_pitch}。"
            )
        result = _OFABuffer(
            handle=handle,
            device_ptr=device_ptr,
            pitch_bytes=pitch,
            width=int(width),
            height=int(height),
            bytes_per_pixel=int(bytes_per_pixel),
        )
        self._buffers.append(result)
        return result

    # ------------------------------- execution ----------------------------

    def _copy_2d_device_to_device(
        self,
        *,
        src_ptr: int,
        src_pitch: int,
        dst_ptr: int,
        dst_pitch: int,
        width_bytes: int,
        height: int,
        stream_ptr: int,
    ) -> None:
        copy = CUDA_MEMCPY2D()
        copy.srcMemoryType = CU_MEMORYTYPE_DEVICE
        copy.srcDevice = int(src_ptr)
        copy.srcPitch = int(src_pitch)
        copy.dstMemoryType = CU_MEMORYTYPE_DEVICE
        copy.dstDevice = int(dst_ptr)
        copy.dstPitch = int(dst_pitch)
        copy.WidthInBytes = int(width_bytes)
        copy.Height = int(height)
        self._check_cuda(
            self._cu_memcpy_2d_async(
                ctypes.byref(copy), ctypes.c_void_p(int(stream_ptr))
            ),
            "cuMemcpy2DAsync",
        )

    def _validate_frame(self, frame: torch.Tensor, name: str) -> torch.Tensor:
        if not isinstance(frame, torch.Tensor):
            raise TypeError(f"{name} 必须是 torch.Tensor。")
        if frame.device.type != "cuda":
            raise ValueError(f"{name} 必须位于 CUDA 显存。")
        index = frame.device.index
        if index is None:
            index = torch.cuda.current_device()
        if index != self.gpu_id:
            raise ValueError(
                f"{name} 位于 cuda:{index}，NVOF 会话位于 cuda:{self.gpu_id}。"
            )
        if frame.dtype != torch.uint8:
            raise ValueError(f"{name}.dtype 必须是 torch.uint8。")
        if tuple(frame.shape) != (self.height, self.width):
            raise ValueError(
                f"{name}.shape 必须是 {(self.height, self.width)}，"
                f"实际为 {tuple(frame.shape)}。"
            )
        return frame if frame.is_contiguous() else frame.contiguous()

    def _execute_internal(
        self,
        input_frame: torch.Tensor,
        reference_frame: torch.Tensor,
        *,
        disable_temporal_hints: bool,
        convert_to_float: bool,
        copy_result: bool,
    ) -> tuple[OFAResult, Optional[OFAResult]]:
        if self._closed:
            raise NVOFError("NVOF 会话已经关闭。")
        input_frame = self._validate_frame(input_frame, "input_frame")
        reference_frame = self._validate_frame(reference_frame, "reference_frame")

        slot_index = self._next_slot
        self._next_slot = (self._next_slot + 1) % self.buffer_count
        slot = self._slots[slot_index]
        if slot.in_use:
            self.input_stream.wait_event(slot.ready_event)

        current_stream = torch.cuda.current_stream(self.device)
        self.input_stream.wait_stream(current_stream)
        input_stream_ptr = int(self.input_stream.cuda_stream)
        output_stream_ptr = int(self.output_stream.cuda_stream)

        self._copy_2d_device_to_device(
            src_ptr=input_frame.data_ptr(),
            src_pitch=self.width,
            dst_ptr=slot.input_a.device_ptr,
            dst_pitch=slot.input_a.pitch_bytes,
            width_bytes=self.width,
            height=self.height,
            stream_ptr=input_stream_ptr,
        )
        self._copy_2d_device_to_device(
            src_ptr=reference_frame.data_ptr(),
            src_pitch=self.width,
            dst_ptr=slot.input_b.device_ptr,
            dst_pitch=slot.input_b.pitch_bytes,
            width_bytes=self.width,
            height=self.height,
            stream_ptr=input_stream_ptr,
        )

        in_params = NV_OF_EXECUTE_INPUT_PARAMS()
        in_params.inputFrame = slot.input_a.handle
        in_params.referenceFrame = slot.input_b.handle
        in_params.externalHints = None
        in_params.disableTemporalHints = int(bool(disable_temporal_hints))
        in_params.padding = 0
        in_params.hPrivData = None
        in_params.padding2 = 0
        in_params.numRois = 0
        in_params.roiData = None

        out_params = NV_OF_EXECUTE_OUTPUT_PARAMS()
        out_params.outputBuffer = slot.output.handle
        out_params.outputCostBuffer = (
            slot.cost_buffer.handle if slot.cost_buffer is not None else None
        )
        out_params.hPrivData = None
        out_params.bwdOutputBuffer = (
            slot.backward_output.handle
            if slot.backward_output is not None
            else None
        )
        out_params.bwdOutputCostBuffer = (
            slot.backward_cost_buffer.handle
            if slot.backward_cost_buffer is not None
            else None
        )
        out_params.globalFlowBuffer = None

        self._check_of(
            self.api.nvOFExecute(
                self.h_of, ctypes.byref(in_params), ctypes.byref(out_params)
            ),
            "nvOFExecute",
        )

        flow_row_bytes = self.out_width * 2 * slot.raw_flow.element_size()
        self._copy_2d_device_to_device(
            src_ptr=slot.output.device_ptr,
            src_pitch=slot.output.pitch_bytes,
            dst_ptr=slot.raw_flow.data_ptr(),
            dst_pitch=flow_row_bytes,
            width_bytes=flow_row_bytes,
            height=self.out_height,
            stream_ptr=output_stream_ptr,
        )
        if slot.cost_buffer is not None and slot.cost_tensor is not None:
            self._copy_2d_device_to_device(
                src_ptr=slot.cost_buffer.device_ptr,
                src_pitch=slot.cost_buffer.pitch_bytes,
                dst_ptr=slot.cost_tensor.data_ptr(),
                dst_pitch=self.out_width,
                width_bytes=self.out_width,
                height=self.out_height,
                stream_ptr=output_stream_ptr,
            )

        if (
            self.bidirectional
            and slot.backward_output is not None
            and slot.backward_raw_flow is not None
        ):
            self._copy_2d_device_to_device(
                src_ptr=slot.backward_output.device_ptr,
                src_pitch=slot.backward_output.pitch_bytes,
                dst_ptr=slot.backward_raw_flow.data_ptr(),
                dst_pitch=flow_row_bytes,
                width_bytes=flow_row_bytes,
                height=self.out_height,
                stream_ptr=output_stream_ptr,
            )
            if (
                slot.backward_cost_buffer is not None
                and slot.backward_cost_tensor is not None
            ):
                self._copy_2d_device_to_device(
                    src_ptr=slot.backward_cost_buffer.device_ptr,
                    src_pitch=slot.backward_cost_buffer.pitch_bytes,
                    dst_ptr=slot.backward_cost_tensor.data_ptr(),
                    dst_pitch=self.out_width,
                    width_bytes=self.out_width,
                    height=self.out_height,
                    stream_ptr=output_stream_ptr,
                )

        if convert_to_float:
            with torch.cuda.stream(self.output_stream):
                slot.flow.copy_(slot.raw_flow).mul_(1.0 / 32.0)
                if (
                    slot.backward_flow is not None
                    and slot.backward_raw_flow is not None
                ):
                    slot.backward_flow.copy_(slot.backward_raw_flow).mul_(1.0 / 32.0)

        slot.ready_event.record(self.output_stream)
        slot.in_use = True
        current_stream.wait_stream(self.output_stream)

        def result(
            raw: torch.Tensor,
            flow: Optional[torch.Tensor],
            cost: Optional[torch.Tensor],
        ) -> OFAResult:
            if copy_result:
                raw = raw.clone()
                flow = flow.clone() if flow is not None else None
                cost = cost.clone() if cost is not None else None
            return OFAResult(
                raw_flow=raw,
                flow=flow,
                cost=cost,
                grid_size=self.grid_size,
                input_width=self.width,
                input_height=self.height,
                slot_index=slot_index,
            )

        forward = result(
            slot.raw_flow,
            slot.flow if convert_to_float else None,
            slot.cost_tensor,
        )
        backward = None
        if self.bidirectional:
            assert slot.backward_raw_flow is not None
            backward = result(
                slot.backward_raw_flow,
                slot.backward_flow if convert_to_float else None,
                slot.backward_cost_tensor,
            )
        return forward, backward

    def execute(
        self,
        input_frame: torch.Tensor,
        reference_frame: torch.Tensor,
        *,
        disable_temporal_hints: bool = False,
        convert_to_float: bool = True,
        copy_result: bool = False,
    ) -> OFAResult:
        """执行一对帧并返回前向光流。

        当会话以 ``bidirectional=True`` 初始化时，驱动仍会在同一次
        ``NvOFExecute`` 中同时生成后向光流；本方法只返回前向结果。
        需要两个方向时使用 :meth:`execute_bidirectional`。
        """
        forward, _ = self._execute_internal(
            input_frame,
            reference_frame,
            disable_temporal_hints=disable_temporal_hints,
            convert_to_float=convert_to_float,
            copy_result=copy_result,
        )
        return forward

    def execute_bidirectional(
        self,
        previous_frame: torch.Tensor,
        current_frame: torch.Tensor,
        *,
        disable_temporal_hints: bool = False,
        convert_to_float: bool = False,
        copy_result: bool = False,
    ) -> tuple[OFAResult, OFAResult]:
        """在单次 SDK 5.0 ``NvOFExecute`` 中生成前向和后向光流。"""
        if not self.bidirectional:
            raise NVOFError(
                "当前会话未启用双向输出；创建时设置 bidirectional=True。"
            )
        forward, backward = self._execute_internal(
            previous_frame,
            current_frame,
            disable_temporal_hints=disable_temporal_hints,
            convert_to_float=convert_to_float,
            copy_result=copy_result,
        )
        assert backward is not None
        return forward, backward

    def synchronize(self) -> None:
        """等待该引擎输出 Stream 完成；仅用于测试、关闭或显式同步。"""
        self.output_stream.synchronize()

    # ------------------------------- errors -------------------------------

    def _last_of_error(self) -> str:
        if not self.h_of.value:
            return ""
        try:
            buffer = ctypes.create_string_buffer(1024)
            size = ctypes.c_uint32(len(buffer))
            status = self.api.nvOFGetLastError(
                self.h_of, buffer, ctypes.byref(size)
            )
            if status == NV_OF_STATUS.SUCCESS:
                return buffer.value.decode("utf-8", errors="replace")
        except BaseException:
            pass
        return ""

    def _check_of(
        self,
        status: int,
        operation: str,
        *,
        allow_no_handle: bool = False,
    ) -> None:
        if int(status) == NV_OF_STATUS.SUCCESS:
            return
        detail = "" if allow_no_handle else self._last_of_error()
        suffix = f"；驱动信息：{detail}" if detail else ""
        raise NVOFError(
            f"{operation} 失败：{NV_OF_STATUS.name(status)}{suffix}"
        )

    def _cuda_error_string(self, status: int) -> str:
        text = ctypes.c_char_p()
        try:
            if self.cuda.cuGetErrorString(status, ctypes.byref(text)) == 0:
                if text.value:
                    return text.value.decode("utf-8", errors="replace")
        except BaseException:
            pass
        return f"CUDA error {status}"

    def _check_cuda(self, status: int, operation: str) -> None:
        if int(status) != 0:
            raise NVOFError(
                f"{operation} 失败：{self._cuda_error_string(int(status))}"
            )

    @property
    def api_version_text(self) -> str:
        return f"{NV_OF_API_MAJOR_VERSION}.{NV_OF_API_MINOR_VERSION}"

    @property
    def driver_api_version_text(self) -> str:
        value = self.driver_api_version
        if not value:
            return "unknown"
        return f"{value >> 4}.{value & 0xF}"

    @property
    def prediction_direction(self) -> str:
        return "both" if self.bidirectional else "forward"

    @property
    def supported_grid_sizes(self) -> tuple[int, ...]:
        return tuple(self._get_caps(NV_OF_CAPS.SUPPORTED_OUTPUT_GRID_SIZES))

    def close(self) -> None:
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            if torch.cuda.is_available():
                self.input_stream.synchronize()
                self.output_stream.synchronize()
        except BaseException:
            pass

        api = getattr(self, "api", None)
        if api is not None:
            for buffer in reversed(getattr(self, "_buffers", [])):
                try:
                    if buffer.handle and buffer.handle.value:
                        api.nvOFDestroyGPUBufferCuda(buffer.handle)
                except BaseException:
                    pass
            self._buffers.clear()
            self._slots.clear()
            try:
                if self.h_of and self.h_of.value:
                    api.nvOFDestroy(self.h_of)
            except BaseException:
                pass
        self.h_of = ctypes.c_void_p()

    def __enter__(self) -> "NvidiaOpticalFlowCuda":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass

# ---------------------------------------------------------------------------
# Fused CUDA/NVRTC offset estimator
# ---------------------------------------------------------------------------

_FUSED_OFFSET_CUDA = r"""
struct Short2 { short x; short y; };

__device__ __forceinline__ float clampf_local(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

__device__ __forceinline__ Short2 load_short2(
    const Short2* ptr, int x, int y, int width, int height
) {
    x = x < 0 ? 0 : (x >= width ? width - 1 : x);
    y = y < 0 ? 0 : (y >= height ? height - 1 : y);
    return ptr[y * width + x];
}

__device__ __forceinline__ void sample_backward(
    const Short2* backward,
    float x,
    float y,
    int width,
    int height,
    float* out_x,
    float* out_y
) {
    int x0 = (int)floorf(x);
    int y0 = (int)floorf(y);
    int x1 = x0 + 1;
    int y1 = y0 + 1;
    float tx = x - (float)x0;
    float ty = y - (float)y0;
    Short2 a = load_short2(backward, x0, y0, width, height);
    Short2 b = load_short2(backward, x1, y0, width, height);
    Short2 c = load_short2(backward, x0, y1, width, height);
    Short2 d = load_short2(backward, x1, y1, width, height);
    float ax = (float)a.x * (1.0f / 32.0f);
    float ay = (float)a.y * (1.0f / 32.0f);
    float bx = (float)b.x * (1.0f / 32.0f);
    float by = (float)b.y * (1.0f / 32.0f);
    float cx = (float)c.x * (1.0f / 32.0f);
    float cy = (float)c.y * (1.0f / 32.0f);
    float dx = (float)d.x * (1.0f / 32.0f);
    float dy = (float)d.y * (1.0f / 32.0f);
    float top_x = ax + (bx - ax) * tx;
    float top_y = ay + (by - ay) * tx;
    float bot_x = cx + (dx - cx) * tx;
    float bot_y = cy + (dy - cy) * tx;
    *out_x = top_x + (bot_x - top_x) * ty;
    *out_y = top_y + (bot_y - top_y) * ty;
}

__device__ __forceinline__ bool vector_valid(
    int index,
    const Short2* forward,
    const unsigned char* cost,
    const Short2* backward,
    const unsigned char* mask,
    int width,
    int height,
    int grid_size,
    int cost_threshold,
    float max_displacement,
    float fb_threshold,
    int has_cost,
    int use_backward,
    float* flow_x,
    float* flow_y,
    int* cost_value,
    bool* before_fb
) {
    if (!mask[index]) return false;
    Short2 raw = forward[index];
    float fx = (float)raw.x * (1.0f / 32.0f);
    float fy = (float)raw.y * (1.0f / 32.0f);
    if (fabsf(fx) > max_displacement || fabsf(fy) > max_displacement) {
        return false;
    }
    int cv = has_cost ? (int)cost[index] : 0;
    if (has_cost && cv > cost_threshold) return false;
    *before_fb = true;

    if (use_backward) {
        int gx = index % width;
        int gy = index / width;
        float end_x = (float)gx + fx / (float)grid_size;
        float end_y = (float)gy + fy / (float)grid_size;
        if (
            end_x < 0.0f || end_y < 0.0f ||
            end_x > (float)(width - 1) ||
            end_y > (float)(height - 1)
        ) return false;
        float bx, by;
        sample_backward(backward, end_x, end_y, width, height, &bx, &by);
        float ex = fx + bx;
        float ey = fy + by;
        if (ex * ex + ey * ey > fb_threshold * fb_threshold) return false;
    }

    *flow_x = fx;
    *flow_y = fy;
    *cost_value = cv;
    return true;
}

extern "C" __global__ void build_histogram(
    const Short2* forward,
    const unsigned char* cost,
    const Short2* backward,
    const unsigned char* mask,
    int n,
    int width,
    int height,
    int grid_size,
    int cost_threshold,
    float bin_size,
    int max_bin,
    int axis_bins,
    float max_displacement,
    float fb_threshold,
    int has_cost,
    int use_backward,
    unsigned int* histogram,
    float* accum
) {
    int index = (int)(blockIdx.x * blockDim.x + threadIdx.x);
    if (index >= n) return;

    float fx = 0.0f, fy = 0.0f;
    int cv = 0;
    bool before_fb = false;
    bool valid = vector_valid(
        index, forward, cost, backward, mask, width, height, grid_size,
        cost_threshold, max_displacement, fb_threshold, has_cost,
        use_backward, &fx, &fy, &cv, &before_fb
    );
    if (before_fb) atomicAdd(&accum[0], 1.0f);
    if (!valid) return;

    int qx = (int)roundf(fx / bin_size);
    int qy = (int)roundf(fy / bin_size);
    qx = qx < -max_bin ? -max_bin : (qx > max_bin ? max_bin : qx);
    qy = qy < -max_bin ? -max_bin : (qy > max_bin ? max_bin : qy);
    int linear = (qy + max_bin) * axis_bins + (qx + max_bin);
    unsigned int weight = (unsigned int)(has_cost ? (256 - cv) : 256);
    atomicAdd(&histogram[linear], weight);
    atomicAdd(&accum[1], 1.0f);
    atomicAdd(&accum[2], (float)weight);
    atomicAdd(&accum[3], (float)cv);
}

extern "C" __global__ void find_peak(
    const unsigned int* histogram,
    int histogram_size,
    int* peak_meta
) {
    extern __shared__ unsigned char shared_raw[];
    unsigned int* shared_value = (unsigned int*)shared_raw;
    int* shared_index = (int*)(shared_value + blockDim.x);
    unsigned int best_value = 0;
    int best_index = 0;
    for (int i = (int)threadIdx.x; i < histogram_size; i += (int)blockDim.x) {
        unsigned int value = histogram[i];
        if (value > best_value) {
            best_value = value;
            best_index = i;
        }
    }
    shared_value[threadIdx.x] = best_value;
    shared_index[threadIdx.x] = best_index;
    __syncthreads();

    for (unsigned int stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
        if (threadIdx.x < stride) {
            unsigned int other = shared_value[threadIdx.x + stride];
            if (other > shared_value[threadIdx.x]) {
                shared_value[threadIdx.x] = other;
                shared_index[threadIdx.x] = shared_index[threadIdx.x + stride];
            }
        }
        __syncthreads();
    }
    if (threadIdx.x == 0) {
        peak_meta[0] = shared_index[0];
        peak_meta[1] = (int)shared_value[0];
    }
}

extern "C" __global__ void refine_peak(
    const Short2* forward,
    const unsigned char* cost,
    const Short2* backward,
    const unsigned char* mask,
    int n,
    int width,
    int height,
    int grid_size,
    int cost_threshold,
    float bin_size,
    int max_bin,
    int axis_bins,
    float max_displacement,
    float fb_threshold,
    float peak_radius,
    int has_cost,
    int use_backward,
    const int* peak_meta,
    float* accum
) {
    int index = (int)(blockIdx.x * blockDim.x + threadIdx.x);
    if (index >= n) return;

    float fx = 0.0f, fy = 0.0f;
    int cv = 0;
    bool before_fb = false;
    if (!vector_valid(
        index, forward, cost, backward, mask, width, height, grid_size,
        cost_threshold, max_displacement, fb_threshold, has_cost,
        use_backward, &fx, &fy, &cv, &before_fb
    )) return;

    int peak_index = peak_meta[0];
    int peak_y = peak_index / axis_bins - max_bin;
    int peak_x = peak_index - (peak_y + max_bin) * axis_bins - max_bin;
    float center_x = (float)peak_x * bin_size;
    float center_y = (float)peak_y * bin_size;
    float rx = fx - center_x;
    float ry = fy - center_y;
    float r2 = rx * rx + ry * ry;
    if (r2 > peak_radius * peak_radius) return;

    float weight = (float)(has_cost ? (256 - cv) : 256);
    atomicAdd(&accum[4], weight);
    atomicAdd(&accum[5], weight * fx);
    atomicAdd(&accum[6], weight * fy);
    atomicAdd(&accum[7], weight * (fx * fx + fy * fy));
    atomicAdd(&accum[8], 1.0f);
}

extern "C" __global__ void finalize_offset(
    const float* accum,
    const int* peak_meta,
    int active_count,
    float* output
) {
    if (threadIdx.x != 0 || blockIdx.x != 0) return;
    float pre_fb = accum[0];
    float valid = accum[1];
    float total_weight = accum[2];
    float cost_sum = accum[3];
    float weight_sum = accum[4];
    float dx = weight_sum > 0.0f ? accum[5] / weight_sum : 0.0f;
    float dy = weight_sum > 0.0f ? accum[6] / weight_sum : 0.0f;
    float variance = weight_sum > 0.0f ? (accum[7] / weight_sum - dx * dx - dy * dy) : 1.0e12f;
    float dispersion = sqrtf(fmaxf(variance, 0.0f));
    float inliers = accum[8];
    float valid_ratio = active_count > 0 ? valid / (float)active_count : 0.0f;
    float inlier_ratio = valid > 0.0f ? inliers / valid : 0.0f;
    float peak_ratio = total_weight > 0.0f ? (float)peak_meta[1] / total_weight : 0.0f;
    float cost_mean = valid > 0.0f ? cost_sum / valid : 255.0f;
    float fb_valid_ratio = pre_fb > 0.0f ? valid / pre_fb : 0.0f;
    float confidence =
        valid_ratio *
        sqrtf(fmaxf(peak_ratio, 0.0f)) *
        inlier_ratio *
        expf(-dispersion / 3.0f) *
        sqrtf(fmaxf(fb_valid_ratio, 0.0f));
    confidence = clampf_local(confidence, 0.0f, 1.0f);

    output[0] = dx;
    output[1] = dy;
    output[2] = dispersion;
    output[3] = valid_ratio;
    output[4] = inlier_ratio;
    output[5] = peak_ratio;
    output[6] = confidence;
    output[7] = cost_mean;
    output[8] = fb_valid_ratio;
}
"""


def _find_nvrtc_dll() -> str:
    candidates: list[str] = []
    found = ctypes.util.find_library("nvrtc")
    if found:
        candidates.append(found)

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        candidates.extend(glob.glob(os.path.join(cuda_path, "bin", "nvrtc64_*.dll")))

    torch_root = os.path.dirname(torch.__file__)
    candidates.extend(glob.glob(os.path.join(torch_root, "lib", "nvrtc64_*.dll")))
    candidates.extend(glob.glob(os.path.join(torch_root, "..", "lib", "nvrtc64_*.dll")))

    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry:
            candidates.extend(glob.glob(os.path.join(entry, "nvrtc64_*.dll")))

    seen: set[str] = set()
    for path in candidates:
        normalized = os.path.abspath(path) if os.path.sep in path else path
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            ctypes.WinDLL(normalized)
            return normalized
        except OSError:
            continue
    raise NVOFError(
        "未找到 nvrtc64_*.dll。融合 CUDA 后处理需要 CUDA Toolkit/NVRTC；"
        "可以使用 backend='torch' 回退到 PyTorch 多算子实现。"
    )


class _NvrtcModule:
    def __init__(self, source: str, device: torch.device) -> None:
        if os.name != "nt":
            raise OSError("NVRTC 融合后处理版本面向 Windows。")
        self.device = device
        self.cuda = _load_system_dll("nvcuda.dll")
        self.nvrtc_path = _find_nvrtc_dll()
        self.nvrtc = ctypes.WinDLL(self.nvrtc_path)
        self.module = ctypes.c_void_p()
        self.functions: dict[str, ctypes.c_void_p] = {}
        self._configure_cuda()
        self._configure_nvrtc()
        self._compile(source)

    def _configure_cuda(self) -> None:
        self.cuda.cuModuleLoadDataEx.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.cuda.cuModuleLoadDataEx.restype = ctypes.c_int
        self.cuda.cuModuleGetFunction.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        self.cuda.cuModuleGetFunction.restype = ctypes.c_int
        self.cuda.cuLaunchKernel.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
        ]
        self.cuda.cuLaunchKernel.restype = ctypes.c_int
        self.cuda.cuModuleUnload.argtypes = [ctypes.c_void_p]
        self.cuda.cuModuleUnload.restype = ctypes.c_int
        self.cuda.cuMemsetD32Async.argtypes = [
            ctypes.c_uint64, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p
        ]
        self.cuda.cuMemsetD32Async.restype = ctypes.c_int
        self.cuda.cuGetErrorString.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)
        ]
        self.cuda.cuGetErrorString.restype = ctypes.c_int

    def _configure_nvrtc(self) -> None:
        self.nvrtc.nvrtcCreateProgram.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.nvrtc.nvrtcCreateProgram.restype = ctypes.c_int
        self.nvrtc.nvrtcCompileProgram.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        self.nvrtc.nvrtcCompileProgram.restype = ctypes.c_int
        self.nvrtc.nvrtcGetPTXSize.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)
        ]
        self.nvrtc.nvrtcGetPTXSize.restype = ctypes.c_int
        self.nvrtc.nvrtcGetPTX.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.nvrtc.nvrtcGetPTX.restype = ctypes.c_int
        self.nvrtc.nvrtcGetProgramLogSize.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)
        ]
        self.nvrtc.nvrtcGetProgramLogSize.restype = ctypes.c_int
        self.nvrtc.nvrtcGetProgramLog.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.nvrtc.nvrtcGetProgramLog.restype = ctypes.c_int
        self.nvrtc.nvrtcDestroyProgram.argtypes = [
            ctypes.POINTER(ctypes.c_void_p)
        ]
        self.nvrtc.nvrtcDestroyProgram.restype = ctypes.c_int

    def _cuda_error(self, status: int) -> str:
        text = ctypes.c_char_p()
        if self.cuda.cuGetErrorString(status, ctypes.byref(text)) == 0 and text.value:
            return text.value.decode("utf-8", errors="replace")
        return f"CUDA error {status}"

    def _check_cuda(self, status: int, operation: str) -> None:
        if status != 0:
            raise NVOFError(f"{operation} 失败：{self._cuda_error(status)}")

    def _nvrtc_log(self, program: ctypes.c_void_p) -> str:
        size = ctypes.c_size_t()
        self.nvrtc.nvrtcGetProgramLogSize(program, ctypes.byref(size))
        if size.value <= 1:
            return ""
        buffer = ctypes.create_string_buffer(size.value)
        self.nvrtc.nvrtcGetProgramLog(program, buffer)
        return buffer.value.decode("utf-8", errors="replace")

    def _compile(self, source: str) -> None:
        program = ctypes.c_void_p()
        status = self.nvrtc.nvrtcCreateProgram(
            ctypes.byref(program),
            source.encode("utf-8"),
            b"ofa_fused_offset.cu",
            0,
            None,
            None,
        )
        if status != 0:
            raise NVOFError(f"nvrtcCreateProgram 失败，状态码 {status}。")
        try:
            major, minor = torch.cuda.get_device_capability(self.device)
            options = [
                b"--std=c++14",
                b"--use_fast_math",
                f"--gpu-architecture=compute_{major}{minor}".encode("ascii"),
            ]
            option_array = (ctypes.c_char_p * len(options))(*options)
            status = self.nvrtc.nvrtcCompileProgram(
                program, len(options), option_array
            )
            log = self._nvrtc_log(program)
            if status != 0:
                raise NVOFError(
                    f"NVRTC 编译融合后处理失败，状态码 {status}：\n{log}"
                )
            ptx_size = ctypes.c_size_t()
            if self.nvrtc.nvrtcGetPTXSize(program, ctypes.byref(ptx_size)) != 0:
                raise NVOFError("nvrtcGetPTXSize 失败。")
            ptx = ctypes.create_string_buffer(ptx_size.value)
            if self.nvrtc.nvrtcGetPTX(program, ptx) != 0:
                raise NVOFError("nvrtcGetPTX 失败。")
            self._ptx = ptx
            self._check_cuda(
                self.cuda.cuModuleLoadDataEx(
                    ctypes.byref(self.module),
                    ctypes.cast(ptx, ctypes.c_void_p),
                    0,
                    None,
                    None,
                ),
                "cuModuleLoadDataEx",
            )
        finally:
            self.nvrtc.nvrtcDestroyProgram(ctypes.byref(program))

    def function(self, name: str) -> ctypes.c_void_p:
        if name not in self.functions:
            function = ctypes.c_void_p()
            self._check_cuda(
                self.cuda.cuModuleGetFunction(
                    ctypes.byref(function), self.module, name.encode("ascii")
                ),
                f"cuModuleGetFunction({name})",
            )
            self.functions[name] = function
        return self.functions[name]

    def memset_d32(
        self, tensor: torch.Tensor, value: int, words: int, stream: int
    ) -> None:
        self._check_cuda(
            self.cuda.cuMemsetD32Async(
                tensor.data_ptr(), value, words, ctypes.c_void_p(stream)
            ),
            "cuMemsetD32Async",
        )

    def launch(
        self,
        name: str,
        grid: tuple[int, int, int],
        block: tuple[int, int, int],
        shared_bytes: int,
        stream: int,
        args: list[ctypes._SimpleCData],
    ) -> None:
        pointers = (ctypes.c_void_p * len(args))(
            *[ctypes.cast(ctypes.byref(arg), ctypes.c_void_p) for arg in args]
        )
        self._check_cuda(
            self.cuda.cuLaunchKernel(
                self.function(name),
                *grid,
                *block,
                shared_bytes,
                ctypes.c_void_p(stream),
                pointers,
                None,
            ),
            f"cuLaunchKernel({name})",
        )

    def close(self) -> None:
        if self.module and self.module.value:
            self.cuda.cuModuleUnload(self.module)
            self.module = ctypes.c_void_p()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass


_FUSED_MODULE_CACHE: dict[tuple[int, int, int], _NvrtcModule] = {}


def _get_fused_module(device: torch.device) -> _NvrtcModule:
    index = device.index if device.index is not None else torch.cuda.current_device()
    capability = torch.cuda.get_device_capability(device)
    key = (index, capability[0], capability[1])
    module = _FUSED_MODULE_CACHE.get(key)
    if module is None:
        module = _NvrtcModule(_FUSED_OFFSET_CUDA, device)
        _FUSED_MODULE_CACHE[key] = module
    return module


class TorchHistogramOffsetEstimator:
    """V3 的 PyTorch 多算子后处理，作为 NVRTC 不可用时的兼容回退。"""

    def __init__(
        self,
        activity_mask: torch.Tensor,
        *,
        grid_size: int,
        cost_threshold: int = 64,
        bin_size: float = 0.5,
        peak_radius: float = 1.75,
        max_displacement: float = 128.0,
        fb_threshold: float = 2.0,
    ) -> None:
        if activity_mask.dtype != torch.bool or activity_mask.device.type != "cuda":
            raise ValueError("activity_mask 必须是 CUDA bool Tensor。")
        self.height, self.width = activity_mask.shape
        self.grid_size = int(grid_size)
        self.indices = activity_mask.reshape(-1).nonzero(as_tuple=False).flatten()
        if self.indices.numel() < 8:
            raise ValueError("活动区域包含的网格过少。")
        self.active_count = float(self.indices.numel())
        self.cost_threshold = int(max(0, min(255, cost_threshold)))
        self.bin_size = float(bin_size)
        self.peak_radius = float(peak_radius)
        self.max_displacement = float(max_displacement)
        self.fb_threshold = float(fb_threshold)
        self.max_bin = int(__import__("math").ceil(self.max_displacement / self.bin_size))
        self.axis_bins = self.max_bin * 2 + 1
        self.histogram_size = self.axis_bins * self.axis_bins
        self.device = activity_mask.device
        flat_y = torch.div(self.indices, self.width, rounding_mode="floor").float()
        flat_x = torch.remainder(self.indices, self.width).float()
        self.grid_x = flat_x
        self.grid_y = flat_y

    def _backward_consistency_mask(
        self, vectors: torch.Tensor, backward: OFAResult
    ) -> torch.Tensor:
        backward_flow = (
            backward.raw_flow.float().mul(1.0 / 32.0)
            if backward.flow is None
            else backward.flow
        )
        end_x = self.grid_x + vectors[:, 0] / self.grid_size
        end_y = self.grid_y + vectors[:, 1] / self.grid_size
        inside = (
            (end_x >= 0.0) & (end_x <= self.width - 1)
            & (end_y >= 0.0) & (end_y <= self.height - 1)
        )
        norm_x = end_x.mul(2.0 / max(1, self.width - 1)).sub_(1.0)
        norm_y = end_y.mul(2.0 / max(1, self.height - 1)).sub_(1.0)
        sample_grid = torch.stack((norm_x, norm_y), dim=-1).view(1, -1, 1, 2)
        sampled = F.grid_sample(
            backward_flow.permute(2, 0, 1).unsqueeze(0),
            sample_grid,
            mode="bilinear",
            padding_mode="zeros",
            align_corners=True,
        )[0, :, :, 0].transpose(0, 1)
        error = torch.linalg.vector_norm(vectors + sampled, dim=1)
        return inside & (error <= self.fb_threshold)

    def estimate(
        self, result: OFAResult, backward: Optional[OFAResult] = None
    ) -> OffsetResult:
        selected_raw = torch.index_select(
            result.raw_flow.reshape(-1, 2), 0, self.indices
        )
        vectors = selected_raw.float().mul_(1.0 / 32.0)
        valid = (vectors.abs() <= self.max_displacement).all(dim=1)
        if result.cost is not None:
            costs = torch.index_select(result.cost.reshape(-1), 0, self.indices)
            valid &= costs <= self.cost_threshold
            weights_all = (
                (256.0 - costs.float()).mul_(1.0 / 256.0).clamp_min_(1 / 256)
            )
        else:
            costs = None
            weights_all = torch.ones((vectors.shape[0],), device=self.device)
        before_fb = valid.count_nonzero().clamp_min(1)
        if backward is not None:
            valid &= self._backward_consistency_mask(vectors, backward)
            fb_valid_ratio = valid.count_nonzero().float() / before_fb.float()
        else:
            fb_valid_ratio = torch.ones((), device=self.device)
        vectors = vectors[valid]
        weights = weights_all[valid]
        qx = torch.round(vectors[:, 0] / self.bin_size).to(torch.int64)
        qy = torch.round(vectors[:, 1] / self.bin_size).to(torch.int64)
        qx.clamp_(-self.max_bin, self.max_bin)
        qy.clamp_(-self.max_bin, self.max_bin)
        linear = (qy + self.max_bin) * self.axis_bins + (qx + self.max_bin)
        histogram = torch.bincount(
            linear, weights=weights, minlength=self.histogram_size
        )
        peak_index = histogram.argmax()
        peak_y = (
            torch.div(peak_index, self.axis_bins, rounding_mode="floor")
            - self.max_bin
        )
        peak_x = torch.remainder(peak_index, self.axis_bins) - self.max_bin
        peak_center = torch.stack((peak_x, peak_y)).float().mul_(self.bin_size)
        residual = torch.linalg.vector_norm(vectors - peak_center, dim=1)
        inliers = residual <= self.peak_radius
        inlier_vectors = vectors[inliers]
        inlier_weights = weights[inliers]
        weight_sum = inlier_weights.sum().clamp_min(1e-6)
        offset = (inlier_vectors * inlier_weights[:, None]).sum(dim=0) / weight_sum
        refined = torch.linalg.vector_norm(inlier_vectors - offset, dim=1)
        dispersion = torch.sqrt(
            (refined.square() * inlier_weights).sum() / weight_sum
        )
        valid_ratio = valid.count_nonzero().float() / self.active_count
        inlier_ratio = inliers.count_nonzero().float() / max(1, vectors.shape[0])
        peak_ratio = histogram[peak_index] / histogram.sum().clamp_min(1e-6)
        cost_mean = (
            costs[valid].float().mean()
            if costs is not None
            else torch.zeros((), device=self.device)
        )
        confidence = (
            valid_ratio
            * torch.sqrt(peak_ratio.clamp_min(0.0))
            * inlier_ratio
            * torch.exp(-dispersion / 3.0)
            * torch.sqrt(fb_valid_ratio.clamp_min(0.0))
        ).clamp_(0.0, 1.0)
        return OffsetResult(
            offset, dispersion, valid_ratio, inlier_ratio, peak_ratio,
            confidence, cost_mean, fb_valid_ratio
        )


class FusedOffsetEstimator:
    """NVRTC 即时编译的融合 CUDA 后处理。

    单次 estimate 使用四个短 kernel 完成：
    cost/FB 过滤与直方图、主峰搜索、峰内加权细化、置信度汇总。
    不创建按帧临时 Tensor，也不使用布尔高级索引或 torch.bincount。
    """

    def __init__(
        self,
        activity_mask: torch.Tensor,
        *,
        grid_size: int,
        cost_threshold: int = 64,
        bin_size: float = 0.5,
        peak_radius: float = 1.75,
        max_displacement: float = 128.0,
        fb_threshold: float = 2.0,
        backend: str = "auto",
    ) -> None:
        if activity_mask.dtype != torch.bool or activity_mask.device.type != "cuda":
            raise ValueError("activity_mask 必须是 CUDA bool Tensor。")
        if backend not in ("auto", "cuda", "torch"):
            raise ValueError("backend 必须是 auto、cuda 或 torch。")
        self.device = activity_mask.device
        self.height, self.width = activity_mask.shape
        self.grid_size = int(grid_size)
        self.cost_threshold = int(max(0, min(255, cost_threshold)))
        self.bin_size = float(bin_size)
        self.peak_radius = float(peak_radius)
        self.max_displacement = float(max_displacement)
        self.fb_threshold = float(fb_threshold)
        import math
        self.max_bin = int(math.ceil(self.max_displacement / self.bin_size))
        self.axis_bins = self.max_bin * 2 + 1
        self.histogram_size = self.axis_bins * self.axis_bins
        self.mask = activity_mask.to(torch.uint8).contiguous()
        self.active_count = int(self.mask.count_nonzero().item())
        if self.active_count < 8:
            raise ValueError("活动区域包含的网格过少。")
        self.fallback_reason = ""
        self._fallback: Optional[TorchHistogramOffsetEstimator] = None

        if backend == "torch":
            self._activate_fallback("用户指定 PyTorch 后处理")
            return
        try:
            self.module = _get_fused_module(self.device)
            self.histogram = torch.empty(
                self.histogram_size, dtype=torch.int32, device=self.device
            )
            self.accum = torch.empty(16, dtype=torch.float32, device=self.device)
            self.peak_meta = torch.empty(2, dtype=torch.int32, device=self.device)
            self.output = torch.empty(9, dtype=torch.float32, device=self.device)
            self.backend_name = f"cuda-nvrtc ({os.path.basename(self.module.nvrtc_path)})"
        except BaseException as exc:
            if backend == "cuda":
                raise
            self._activate_fallback(str(exc))

    def _activate_fallback(self, reason: str) -> None:
        self.fallback_reason = reason
        self.backend_name = "torch-fallback"
        self._fallback = TorchHistogramOffsetEstimator(
            self.mask.bool(),
            grid_size=self.grid_size,
            cost_threshold=self.cost_threshold,
            bin_size=self.bin_size,
            peak_radius=self.peak_radius,
            max_displacement=self.max_displacement,
            fb_threshold=self.fb_threshold,
        )

    @staticmethod
    def _ptr(value: int) -> ctypes.c_uint64:
        return ctypes.c_uint64(int(value))

    def estimate(
        self, result: OFAResult, backward: Optional[OFAResult] = None
    ) -> OffsetResult:
        if self._fallback is not None:
            return self._fallback.estimate(result, backward)

        if tuple(result.raw_flow.shape[:2]) != (self.height, self.width):
            raise ValueError("光流尺寸与 estimator activity_mask 不一致。")
        stream = int(torch.cuda.current_stream(self.device).cuda_stream)
        self.module.memset_d32(
            self.histogram, 0, self.histogram.numel(), stream
        )
        self.module.memset_d32(self.accum, 0, self.accum.numel(), stream)
        self.module.memset_d32(self.peak_meta, 0, self.peak_meta.numel(), stream)

        n = self.width * self.height
        threads = 256
        blocks = (n + threads - 1) // threads
        cost_ptr = result.cost.data_ptr() if result.cost is not None else 0
        backward_ptr = backward.raw_flow.data_ptr() if backward is not None else 0
        has_cost = int(result.cost is not None)
        use_backward = int(backward is not None)

        common_args = [
            self._ptr(result.raw_flow.data_ptr()),
            self._ptr(cost_ptr),
            self._ptr(backward_ptr),
            self._ptr(self.mask.data_ptr()),
            ctypes.c_int(n),
            ctypes.c_int(self.width),
            ctypes.c_int(self.height),
            ctypes.c_int(self.grid_size),
            ctypes.c_int(self.cost_threshold),
            ctypes.c_float(self.bin_size),
            ctypes.c_int(self.max_bin),
            ctypes.c_int(self.axis_bins),
            ctypes.c_float(self.max_displacement),
            ctypes.c_float(self.fb_threshold),
        ]
        self.module.launch(
            "build_histogram",
            (blocks, 1, 1),
            (threads, 1, 1),
            0,
            stream,
            common_args
            + [
                ctypes.c_int(has_cost),
                ctypes.c_int(use_backward),
                self._ptr(self.histogram.data_ptr()),
                self._ptr(self.accum.data_ptr()),
            ],
        )
        self.module.launch(
            "find_peak",
            (1, 1, 1),
            (256, 1, 1),
            256 * (ctypes.sizeof(ctypes.c_uint32) + ctypes.sizeof(ctypes.c_int32)),
            stream,
            [
                self._ptr(self.histogram.data_ptr()),
                ctypes.c_int(self.histogram_size),
                self._ptr(self.peak_meta.data_ptr()),
            ],
        )
        self.module.launch(
            "refine_peak",
            (blocks, 1, 1),
            (threads, 1, 1),
            0,
            stream,
            common_args
            + [
                ctypes.c_float(self.peak_radius),
                ctypes.c_int(has_cost),
                ctypes.c_int(use_backward),
                self._ptr(self.peak_meta.data_ptr()),
                self._ptr(self.accum.data_ptr()),
            ],
        )
        self.module.launch(
            "finalize_offset",
            (1, 1, 1),
            (1, 1, 1),
            0,
            stream,
            [
                self._ptr(self.accum.data_ptr()),
                self._ptr(self.peak_meta.data_ptr()),
                ctypes.c_int(self.active_count),
                self._ptr(self.output.data_ptr()),
            ],
        )
        return OffsetResult(
            offset=self.output[0:2],
            dispersion=self.output[2],
            valid_ratio=self.output[3],
            inlier_ratio=self.output[4],
            peak_ratio=self.output[5],
            confidence=self.output[6],
            cost_mean=self.output[7],
            fb_valid_ratio=self.output[8],
        )

