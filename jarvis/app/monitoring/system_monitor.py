import asyncio
import platform
import psutil
import socket
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from collections import deque


@dataclass
class CPUMetrics:
    percent: float
    per_cpu: List[float]
    count_logical: int
    count_physical: int
    freq_current: Optional[float] = None
    freq_min: Optional[float] = None
    freq_max: Optional[float] = None
    load_avg_1m: Optional[float] = None
    load_avg_5m: Optional[float] = None
    load_avg_15m: Optional[float] = None


@dataclass
class MemoryMetrics:
    total: int
    available: int
    used: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass
class DiskMetrics:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class BatteryMetrics:
    percent: float
    power_plugged: bool
    time_left: Optional[int] = None
    status: str = "unknown"


@dataclass
class NetworkInterface:
    name: str
    is_up: bool
    speed: Optional[int] = None
    mtu: Optional[int] = None
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0


@dataclass
class NetworkMetrics:
    interfaces: List[NetworkInterface]
    total_bytes_sent: int = 0
    total_bytes_recv: int = 0
    internet_connected: bool = False


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: Optional[str]
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    memory_vms: int
    status: str
    create_time: datetime
    exe: Optional[str] = None
    cmdline: List[str] = field(default_factory=list)
    num_threads: int = 0


@dataclass
class SystemInfo:
    hostname: str
    platform: str
    platform_version: str
    architecture: str
    processor: str
    boot_time: datetime
    uptime_seconds: int
    python_version: str


@dataclass
class SystemSnapshot:
    timestamp: datetime
    cpu: CPUMetrics
    memory: MemoryMetrics
    disks: List[DiskMetrics]
    battery: Optional[BatteryMetrics]
    network: NetworkMetrics
    processes: List[ProcessInfo]
    system: SystemInfo
    alerts: List[str] = field(default_factory=list)


class SystemMonitor:
    def __init__(self, refresh_interval: int = 2, process_interval: int = 5, network_interval: int = 3):
        self.refresh_interval = refresh_interval
        self.process_interval = process_interval
        self.network_interval = network_interval
        self._history: deque = deque(maxlen=300)
        self._process_history: deque = deque(maxlen=100)
        self._network_history: deque = deque(maxlen=100)
        self._last_snapshot: Optional[SystemSnapshot] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []

    def _check_internet(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def _get_cpu_metrics(self) -> CPUMetrics:
        percent = psutil.cpu_percent(interval=0.1)
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        count_logical = psutil.cpu_count(logical=True)
        count_physical = psutil.cpu_count(logical=False)

        freq = psutil.cpu_freq()
        freq_current = freq.current if freq else None
        freq_min = freq.min if freq else None
        freq_max = freq.max if freq else None

        load_avg = None
        try:
            load_avg = psutil.getloadavg()
        except AttributeError:
            pass

        return CPUMetrics(
            percent=percent,
            per_cpu=per_cpu,
            count_logical=count_logical,
            count_physical=count_physical,
            freq_current=freq_current,
            freq_min=freq_min,
            freq_max=freq_max,
            load_avg_1m=load_avg[0] if load_avg else None,
            load_avg_5m=load_avg[1] if load_avg else None,
            load_avg_15m=load_avg[2] if load_avg else None,
        )

    def _get_memory_metrics(self) -> MemoryMetrics:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return MemoryMetrics(
            total=mem.total,
            available=mem.available,
            used=mem.used,
            percent=mem.percent,
            swap_total=swap.total,
            swap_used=swap.used,
            swap_percent=swap.percent,
        )

    def _get_disk_metrics(self) -> List[DiskMetrics]:
        disks = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append(DiskMetrics(
                    device=partition.device,
                    mountpoint=partition.mountpoint,
                    fstype=partition.fstype,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent,
                ))
            except (PermissionError, OSError):
                continue
        return disks

    def _get_battery_metrics(self) -> Optional[BatteryMetrics]:
        try:
            battery = psutil.sensors_battery()
            if battery:
                return BatteryMetrics(
                    percent=battery.percent,
                    power_plugged=battery.power_plugged,
                    time_left=battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                    status="charging" if battery.power_plugged else "discharging",
                )
        except AttributeError:
            pass
        return None

    def _get_network_metrics(self) -> NetworkMetrics:
        interfaces = []
        total_sent = 0
        total_recv = 0

        net_io = psutil.net_io_counters(pernic=True)
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()

        for name, stats in net_io.items():
            iface = NetworkInterface(
                name=name,
                is_up=net_if_stats.get(name).isup if name in net_if_stats else False,
                speed=net_if_stats.get(name).speed if name in net_if_stats else None,
                mtu=net_if_stats.get(name).mtu if name in net_if_stats else None,
                bytes_sent=stats.bytes_sent,
                bytes_recv=stats.bytes_recv,
                packets_sent=stats.packets_sent,
                packets_recv=stats.packets_recv,
                errin=stats.errin,
                errout=stats.errout,
                dropin=stats.dropin,
                dropout=stats.dropout,
            )

            if name in net_if_addrs:
                for addr in net_if_addrs[name]:
                    if addr.family == socket.AF_INET:
                        iface.ipv4_address = addr.address
                    elif addr.family == socket.AF_INET6:
                        iface.ipv6_address = addr.address
                    elif addr.family == psutil.AF_LINK:
                        iface.mac_address = addr.address

            interfaces.append(iface)
            total_sent += stats.bytes_sent
            total_recv += stats.bytes_recv

        return NetworkMetrics(
            interfaces=interfaces,
            total_bytes_sent=total_sent,
            total_bytes_recv=total_recv,
            internet_connected=self._check_internet(),
        )

    def _get_process_metrics(self, limit: int = 50) -> List[ProcessInfo]:
        processes = []
        for proc in psutil.process_iter([
            'pid', 'name', 'username', 'cpu_percent', 'memory_percent',
            'memory_info', 'status', 'create_time', 'exe', 'cmdline', 'num_threads'
        ]):
            try:
                info = proc.info
                if info['cpu_percent'] is None:
                    continue
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'] or 'Unknown',
                    username=info['username'],
                    cpu_percent=info['cpu_percent'] or 0.0,
                    memory_percent=info['memory_percent'] or 0.0,
                    memory_rss=info['memory_info'].rss if info['memory_info'] else 0,
                    memory_vms=info['memory_info'].vms if info['memory_info'] else 0,
                    status=info['status'] or 'unknown',
                    create_time=datetime.fromtimestamp(info['create_time']) if info['create_time'] else datetime.now(),
                    exe=info['exe'],
                    cmdline=info['cmdline'] or [],
                    num_threads=info['num_threads'] or 0,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        return processes[:limit]

    def _get_system_info(self) -> SystemInfo:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = int((datetime.now() - boot_time).total_seconds())
        return SystemInfo(
            hostname=socket.gethostname(),
            platform=platform.system(),
            platform_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor(),
            boot_time=boot_time,
            uptime_seconds=uptime,
            python_version=platform.python_version(),
        )

    def _generate_alerts(self, snapshot: SystemSnapshot) -> List[str]:
        alerts = []
        if snapshot.cpu.percent > 90:
            alerts.append(f"Critical: CPU usage at {snapshot.cpu.percent:.1f}%")
        elif snapshot.cpu.percent > 75:
            alerts.append(f"Warning: CPU usage at {snapshot.cpu.percent:.1f}%")

        if snapshot.memory.percent > 90:
            alerts.append(f"Critical: Memory usage at {snapshot.memory.percent:.1f}%")
        elif snapshot.memory.percent > 80:
            alerts.append(f"Warning: Memory usage at {snapshot.memory.percent:.1f}%")

        for disk in snapshot.disks:
            if disk.percent > 95:
                alerts.append(f"Critical: Disk {disk.mountpoint} at {disk.percent:.1f}%")
            elif disk.percent > 85:
                alerts.append(f"Warning: Disk {disk.mountpoint} at {disk.percent:.1f}%")

        if snapshot.battery and snapshot.battery.percent < 10 and not snapshot.battery.power_plugged:
            alerts.append(f"Critical: Battery at {snapshot.battery.percent:.1f}%")
        elif snapshot.battery and snapshot.battery.percent < 20 and not snapshot.battery.power_plugged:
            alerts.append(f"Warning: Battery at {snapshot.battery.percent:.1f}%")

        if not snapshot.network.internet_connected:
            alerts.append("Network: No internet connectivity")

        return alerts

    async def take_snapshot(self) -> SystemSnapshot:
        loop = asyncio.get_event_loop()

        cpu = await loop.run_in_executor(None, self._get_cpu_metrics)
        memory = await loop.run_in_executor(None, self._get_memory_metrics)
        disks = await loop.run_in_executor(None, self._get_disk_metrics)
        battery = await loop.run_in_executor(None, self._get_battery_metrics)
        network = await loop.run_in_executor(None, self._get_network_metrics)
        processes = await loop.run_in_executor(None, self._get_process_metrics)
        system = await loop.run_in_executor(None, self._get_system_info)

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=cpu,
            memory=memory,
            disks=disks,
            battery=battery,
            network=network,
            processes=processes,
            system=system,
        )
        snapshot.alerts = self._generate_alerts(snapshot)

        self._history.append(snapshot)
        self._last_snapshot = snapshot
        return snapshot

    async def start(self):
        self._running = True
        self._tasks = [
            asyncio.create_task(self._monitor_loop()),
            asyncio.create_task(self._process_loop()),
            asyncio.create_task(self._network_loop()),
        ]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _monitor_loop(self):
        while self._running:
            try:
                await self.take_snapshot()
            except Exception:
                pass
            await asyncio.sleep(self.refresh_interval)

    async def _process_loop(self):
        while self._running:
            try:
                snapshot = await self.take_snapshot()
                self._process_history.append({
                    'timestamp': snapshot.timestamp,
                    'processes': snapshot.processes,
                })
            except Exception:
                pass
            await asyncio.sleep(self.process_interval)

    async def _network_loop(self):
        while self._running:
            try:
                snapshot = await self.take_snapshot()
                self._network_history.append({
                    'timestamp': snapshot.timestamp,
                    'bytes_sent': snapshot.network.total_bytes_sent,
                    'bytes_recv': snapshot.network.total_bytes_recv,
                })
            except Exception:
                pass
            await asyncio.sleep(self.network_interval)

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def get_latest(self) -> Optional[SystemSnapshot]:
        return self._last_snapshot

    def get_history(self, minutes: int = 5) -> List[SystemSnapshot]:
        cutoff = datetime.now().timestamp() - (minutes * 60)
        return [s for s in self._history if s.timestamp.timestamp() > cutoff]

    def get_process_history(self, minutes: int = 5) -> List[Dict]:
        cutoff = datetime.now().timestamp() - (minutes * 60)
        return [h for h in self._process_history if h['timestamp'].timestamp() > cutoff]

    def get_network_history(self, minutes: int = 5) -> List[Dict]:
        cutoff = datetime.now().timestamp() - (minutes * 60)
        return [h for h in self._network_history if h['timestamp'].timestamp() > cutoff]