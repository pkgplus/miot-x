# -*- coding: utf-8 -*-
"""miot 设备类型 → HomeKit 服务映射。

基于 miot SPEC urn 和设备 model 前缀，将米家设备映射到 HomeKit 服务类型。
"""
from dataclasses import dataclass
from typing import Optional

from pyhap.loader import Loader

_loader = Loader()


@dataclass
class DeviceMapping:
    """单个设备的 HomeKit 映射配置。

    对于多通道设备（如双键墙壁开关），设置 channels 字段，
    每个 channel 的 siid/piid 覆盖默认值。
    """
    # HomeKit 服务名称（如 Lightbulb, Switch, Fan）
    service_name: str
    # 多通道子设备: [(display_name, siid, piid), ...]
    channels: list[tuple[str, int, int]] | None = None
    # 可选附加服务（如温度传感器 + 湿度传感器）
    extra_services: list[str] | None = None
    # miot 开关属性 siid/piid（默认 2/1）
    on_siid: int = 2
    on_piid: int = 1
    # 亮度属性（部分设备支持）
    brightness_siid: int | None = None
    brightness_piid: int | None = None
    # 色温属性
    color_temp_siid: int | None = None
    color_temp_piid: int | None = None
    # 风扇速度属性
    speed_siid: int | None = None
    speed_piid: int | None = None
    # 温度属性（只读）
    temperature_siid: int | None = None
    temperature_piid: int | None = None
    # 湿度属性（只读）
    humidity_siid: int | None = None
    humidity_piid: int | None = None
    # 窗帘位置属性
    position_siid: int | None = None
    position_piid: int | None = None
    # 空调模式/目标温度
    target_temp_siid: int | None = None
    target_temp_piid: int | None = None
    mode_siid: int | None = None
    mode_piid: int | None = None
    # 音量属性（只读）
    volume_siid: int | None = None
    volume_piid: int | None = None
    # 静音属性
    mute_siid: int | None = None
    mute_piid: int | None = None
    # IR 动作映射: {action_name: (siid, aiid)}
    # action_name: power_on, power_off, volume_up, volume_down,
    #   channel_up, channel_down, mute_on, mute_off, input_source
    actions: dict[str, tuple[int, int]] | None = None
    # HomeKit category (see pyhap.const)
    category: int | None = None


# ── 设备模型前缀 → 映射 ──────────────────────────────

_MODEL_MAP: dict[str, DeviceMapping] = {
    # ── 灯 ──
    "yeelink": DeviceMapping(
        service_name="Lightbulb",
        brightness_siid=2, brightness_piid=2,
        color_temp_siid=2, color_temp_piid=4,
    ),
    "philips": DeviceMapping(
        service_name="Lightbulb",
        brightness_siid=2, brightness_piid=2,
        color_temp_siid=2, color_temp_piid=3,
    ),
    # ── 开关 ──
    "lumi.switch": DeviceMapping(service_name="Switch"),
    "lumi.ctrl": DeviceMapping(
        service_name="Switch",
        channels=[
            ("墙壁开关（左键）", 2, 1),
            ("墙壁开关（射灯）", 3, 1),
        ],
    ),
    "ptx.switch": DeviceMapping(service_name="Switch"),
    # ── 插座 ──
    "chuangmi.plug": DeviceMapping(service_name="Outlet"),
    "cuco.plug": DeviceMapping(service_name="Outlet"),
    "zimi.plug": DeviceMapping(service_name="Outlet"),
    # ── 风扇 ──
    "dmaker.fan": DeviceMapping(
        service_name="Fan",
        speed_siid=2, speed_piid=3,
    ),
    "zhimi.fan": DeviceMapping(
        service_name="Fan",
        speed_siid=2, speed_piid=3,
    ),
    # ── 空气净化器 ──
    "zhimi.airpurifier": DeviceMapping(
        service_name="AirPurifier",
        speed_siid=2, speed_piid=3,
    ),
    "dmaker.airpurifier": DeviceMapping(
        service_name="AirPurifier",
        speed_siid=2, speed_piid=3,
    ),
    # ── 空调伴侣 / 空调 ──
    "lumi.acpartner": DeviceMapping(
        service_name="HeaterCooler",
        target_temp_siid=2, target_temp_piid=2,
        mode_siid=2, mode_piid=4,
    ),
    # ── 窗帘 ──
    "lumi.curtain": DeviceMapping(
        service_name="WindowCovering",
        position_siid=2, position_piid=2,
    ),
    "dmaker.curtain": DeviceMapping(
        service_name="WindowCovering",
        position_siid=2, position_piid=2,
    ),
    # ── 传感器（温湿度）────
    "xiaomi.sensor_ht": DeviceMapping(
        service_name="TemperatureSensor",
        extra_services=["HumiditySensor"],
        temperature_siid=2, temperature_piid=1,
        humidity_siid=2, humidity_piid=2,
    ),
    "lumi.sensor_ht": DeviceMapping(
        service_name="TemperatureSensor",
        extra_services=["HumiditySensor"],
        temperature_siid=2, temperature_piid=1,
        humidity_siid=2, humidity_piid=2,
    ),
    "miaomiaoce.sensor_ht": DeviceMapping(
        service_name="TemperatureSensor",
        extra_services=["HumiditySensor"],
        temperature_siid=2, temperature_piid=1,
        humidity_siid=2, humidity_piid=2,
    ),
    # ── 传感器（人体）────
    "lumi.sensor_motion": DeviceMapping(service_name="MotionSensor"),
    "xiaomi.sensor_motion": DeviceMapping(service_name="MotionSensor"),
    # ── 传感器（门磁）────
    "lumi.sensor_magnet": DeviceMapping(service_name="ContactSensor"),
    "xiaomi.sensor_magnet": DeviceMapping(service_name="ContactSensor"),
    # ── 门锁 ──
    "lumi.lock": DeviceMapping(service_name="LockMechanism"),
    "aqara.lock": DeviceMapping(service_name="LockMechanism"),
    # ── 通用开关（墙壁开关等）────────
    "lumi.plug": DeviceMapping(service_name="Switch"),
    # ── 吸顶灯 ──
    "xiaomi.light": DeviceMapping(
        service_name="Lightbulb",
        brightness_siid=2, brightness_piid=2,
        color_temp_siid=2, color_temp_piid=4,
    ),
    "shhf.light": DeviceMapping(
        service_name="Lightbulb",
        brightness_siid=2, brightness_piid=2,
    ),
    "pmfbj.light": DeviceMapping(
        service_name="Lightbulb",
        brightness_siid=2, brightness_piid=2,
    ),
    # ── 门锁 ──
    "loock.lock": DeviceMapping(service_name="LockMechanism"),
    # ── 无线开关/移动开关 ──
    "lumi.sensor_switch": DeviceMapping(service_name="Switch"),
    # ── 红外遥控虚拟设备 ──
    # Television 必须独立发布（非 Bridge 子配件），bridge.py 会单独处理
    "miir.tv": DeviceMapping(
        service_name="Television",
        extra_services=["TelevisionSpeaker"],
        volume_siid=2, volume_piid=1,
        actions={
            "power_on": (2, 5),
            "power_off": (2, 6),
            "volume_up": (2, 4),
            "volume_down": (2, 3),
            "channel_up": (2, 2),
            "channel_down": (2, 1),
            "mute_on": (2, 7),
            "mute_off": (2, 8),
            "input_source": (2, 9),
        },
    ),
    # ── 扫地机器人 ──
    "rockrobo.vacuum": DeviceMapping(service_name="Switch"),
    # ── 音箱 ──
    # HomeKit 不支持第三方 Speaker 服务，改用 Switch（开关静音/取消静音）
    "xiaomi.wifispeaker": DeviceMapping(
        service_name="Switch",
    ),
    # ── 门铃 ──
    # StatelessProgrammableSwitch 的 ProgrammableSwitchEvent 初始化阶段无法设值，
    # iOS 拒绝 value=None 的配件 → 改用 ContactSensor
    "madv.cateye": DeviceMapping(service_name="ContactSensor"),
}


def get_mapping(device_model: str) -> Optional[DeviceMapping]:
    """根据设备 model 获取 HomeKit 映射配置。

    按「最长前缀匹配」查找，确保更具体的规则优先。
    """
    best: Optional[DeviceMapping] = None
    best_len = 0
    for prefix, mapping in _MODEL_MAP.items():
        if device_model.startswith(prefix) and len(prefix) > best_len:
            best = mapping
            best_len = len(prefix)
    return best


def get_service(name: str):
    """从 HAP-python loader 获取预定义服务。"""
    return _loader.get_service(name)


def get_char(name: str):
    """从 HAP-python loader 获取预定义 characteristic。"""
    return _loader.get_char(name)
