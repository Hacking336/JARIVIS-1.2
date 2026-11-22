import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.monitoring.system_monitor import (
    SystemMonitor,
    SystemSnapshot,
    CPUMetrics,
    MemoryMetrics,
    DiskMetrics,
    BatteryMetrics,
    NetworkMetrics,
    NetworkInterface,
    ProcessInfo,
    SystemInfo,
)


class TestCPUMetrics:
    def test_cpu_metrics_creation(self):
        metrics = CPUMetrics(
            percent=45.5,
            per_cpu=[10.0, 20.0, 30.0, 40.0],
            count_logical=4,
            count_physical=2,
            freq_current=3500.0,
            freq_min=800.0,
            freq_max=4000.0,
            load_avg_1m=1.5,
            load_avg_5m=2.0,
            load_avg_15m=1.8,
        )
        assert metrics.percent == 45.5
        assert metrics.count_logical == 4
        assert metrics.count_physical == 2
        assert len(metrics.per_cpu) == 4

    def test_cpu_metrics_with_none_values(self):
        metrics = CPUMetrics(
            percent=0.0,
            per_cpu=[],
            count_logical=0,
            count_physical=0,
        )
        assert metrics.freq_current is None
        assert metrics.load_avg_1m is None


class TestMemoryMetrics:
    def test_memory_metrics_creation(self):
        metrics = MemoryMetrics(
            total=16 * 1024**3,
            available=8 * 1024**3,
            used=8 * 1024**3,
            percent=50.0,
            swap_total=8 * 1024**3,
            swap_used=0,
            swap_percent=0.0,
        )
        assert metrics.total == 16 * 1024**3
        assert metrics.percent == 50.0
        assert metrics.available == 8 * 1024**3


class TestDiskMetrics:
    def test_disk_metrics_creation(self):
        metrics = DiskMetrics(
            device="C:",
            mountpoint="C:\\",
            fstype="NTFS",
            total=500 * 1024**3,
            used=250 * 1024**3,
            free=250 * 1024**3,
            percent=50.0,
        )
        assert metrics.device == "C:"
        assert metrics.percent == 50.0


class TestBatteryMetrics:
    def test_battery_metrics_creation(self):
        metrics = BatteryMetrics(
            percent=75.0,
            power_plugged=False,
            time_left=7200,
            status="discharging",
        )
        assert metrics.percent == 75.0
        assert metrics.power_plugged is False
        assert metrics.status == "discharging"

    def test_battery_metrics_charging(self):
        metrics = BatteryMetrics(
            percent=100.0,
            power_plugged=True,
            time_left=None,
            status="charging",
        )
        assert metrics.power_plugged is True
        assert metrics.status == "charging"


class TestNetworkMetrics:
    def test_network_metrics_creation(self):
        iface = NetworkInterface(
            name="Ethernet",
            is_up=True,
            speed=1000,
            mtu=1500,
            ipv4_address="192.168.1.100",
            mac_address="AA:BB:CC:DD:EE:FF",
            bytes_sent=1000000,
            bytes_recv=5000000,
        )
        metrics = NetworkMetrics(
            interfaces=[iface],
            total_bytes_sent=1000000,
            total_bytes_recv=5000000,
            internet_connected=True,
        )
        assert len(metrics.interfaces) == 1
        assert metrics.internet_connected is True
        assert metrics.interfaces[0].name == "Ethernet"


class TestProcessInfo:
    def test_process_info_creation(self):
        proc = ProcessInfo(
            pid=1234,
            name="notepad.exe",
            username="user",
            cpu_percent=5.5,
            memory_percent=2.0,
            memory_rss=50 * 1024**2,
            memory_vms=100 * 1024**2,
            status="running",
            create_time=datetime.now(),
            exe="C:\\Windows\\notepad.exe",
            cmdline=["notepad.exe"],
            num_threads=2,
        )
        assert proc.pid == 1234
        assert proc.name == "notepad.exe"
        assert proc.cpu_percent == 5.5


class TestSystemSnapshot:
    def test_snapshot_creation(self):
        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=1, count_physical=1),
            memory=MemoryMetrics(total=8*1024**3, available=4*1024**3, used=4*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[],
            battery=None,
            network=NetworkMetrics(interfaces=[], internet_connected=True),
            processes=[],
            system=SystemInfo(
                hostname="TEST-PC",
                platform="Windows",
                platform_version="10.0",
                architecture="AMD64",
                processor="Intel",
                boot_time=datetime.now(),
                uptime_seconds=3600,
                python_version="3.11.0",
            ),
            alerts=[],
        )
        assert snapshot.system.hostname == "TEST-PC"
        assert snapshot.cpu.percent == 50.0
        assert snapshot.network.internet_connected is True


class TestSystemMonitor:
    @pytest.fixture
    def monitor(self):
        return SystemMonitor(refresh_interval=1, process_interval=5, network_interval=3)

    def test_monitor_initialization(self, monitor):
        assert monitor.refresh_interval == 1
        assert monitor.process_interval == 5
        assert monitor.network_interval == 3
        assert monitor._running is False
        assert monitor._last_snapshot is None

    def test_monitor_get_cpu_metrics(self, monitor):
        metrics = monitor._get_cpu_metrics()
        assert isinstance(metrics, CPUMetrics)
        assert 0 <= metrics.percent <= 100
        assert metrics.count_logical > 0
        assert len(metrics.per_cpu) == metrics.count_logical

    def test_monitor_get_memory_metrics(self, monitor):
        metrics = monitor._get_memory_metrics()
        assert isinstance(metrics, MemoryMetrics)
        assert metrics.total > 0
        assert 0 <= metrics.percent <= 100

    def test_monitor_get_disk_metrics(self, monitor):
        metrics = monitor._get_disk_metrics()
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        for disk in metrics:
            assert isinstance(disk, DiskMetrics)
            assert disk.total > 0
            assert 0 <= disk.percent <= 100

    def test_monitor_get_battery_metrics(self, monitor):
        metrics = monitor._get_battery_metrics()
        # Battery may be None on desktop
        assert metrics is None or isinstance(metrics, BatteryMetrics)

    def test_monitor_get_network_metrics(self, monitor):
        metrics = monitor._get_network_metrics()
        assert isinstance(metrics, NetworkMetrics)
        assert isinstance(metrics.interfaces, list)
        assert isinstance(metrics.internet_connected, bool)

    def test_monitor_get_process_metrics(self, monitor):
        metrics = monitor._get_process_metrics(limit=10)
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        for proc in metrics:
            assert isinstance(proc, ProcessInfo)
            assert proc.pid >= 0
            assert proc.name is not None

    def test_monitor_get_system_info(self, monitor):
        info = monitor._get_system_info()
        assert isinstance(info, SystemInfo)
        assert info.hostname is not None
        assert info.platform is not None
        assert info.uptime_seconds >= 0

    def test_monitor_generate_alerts_high_cpu(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 95.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("CPU" in alert for alert in alerts)

    def test_monitor_generate_alerts_high_memory(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 95.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Memory" in alert for alert in alerts)

    def test_monitor_generate_alerts_low_disk(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = [Mock()]
        snapshot.disks[0].mountpoint = "C:\\"
        snapshot.disks[0].percent = 96.0
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Disk" in alert for alert in alerts)

    def test_monitor_generate_alerts_no_internet(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = False

        alerts = monitor._generate_alerts(snapshot)
        assert any("internet" in alert.lower() for alert in alerts)

    def test_monitor_generate_alerts_low_battery(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = Mock()
        snapshot.battery.percent = 5.0
        snapshot.battery.power_plugged = False
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Battery" in alert for alert in alerts)

    def test_monitor_generate_alerts_no_alerts(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_monitor_take_snapshot(self, monitor):
        snapshot = await monitor.take_snapshot()
        assert isinstance(snapshot, SystemSnapshot)
        assert snapshot.cpu is not None
        assert snapshot.memory is not None
        assert snapshot.network is not None
        assert snapshot.system is not None
        assert monitor._last_snapshot is snapshot

    @pytest.mark.asyncio
    async def test_monitor_get_history(self, monitor):
        await monitor.take_snapshot()
        history = monitor.get_history(minutes=5)
        assert isinstance(history, list)
        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_monitor_get_latest(self, monitor):
        await monitor.take_snapshot()
        latest = monitor.get_latest()
        assert isinstance(latest, SystemSnapshot)

    @pytest.mark.asyncio
    async def test_monitor_stop(self, monitor):
        monitor._running = True
        monitor._tasks = []
        await monitor.stop()
        assert monitor._running is False


class TestSystemMonitorEdgeCases:
    @pytest.fixture
    def monitor(self):
        return SystemMonitor()

    def test_process_metrics_with_access_denied(self, monitor):
        # Should handle processes that can't be accessed
        metrics = monitor._get_process_metrics(limit=100)
        assert isinstance(metrics, list)

    def test_disk_metrics_with_permission_error(self, monitor):
        # Should handle disks that can't be accessed
        metrics = monitor._get_disk_metrics()
        assert isinstance(metrics, list)

    def test_network_metrics_with_no_interfaces(self, monitor):
        # Mock empty interfaces
        with patch('psutil.net_io_counters', return_value={}):
            with patch('psutil.net_if_addrs', return_value={}):
                with patch('psutil.net_if_stats', return_value={}):
                    metrics = monitor._get_network_metrics()
                    assert isinstance(metrics, NetworkMetrics)
                    assert len(metrics.interfaces) == 0

    def test_battery_metrics_no_battery(self, monitor):
        # Mock no battery
        with patch('psutil.sensors_battery', return_value=None):
            metrics = monitor._get_battery_metrics()
            assert metrics is None

    def test_internet_check_timeout(self, monitor):
        # Mock socket failure
        with patch('socket.create_connection', side_effect=OSError("No network")):
            connected = monitor._check_internet()
            assert connected is False


class TestSystemMonitorAlerts:
    @pytest.fixture
    def monitor(self):
        return SystemMonitor()

    def test_alert_thresholds(self, monitor):
        # Test warning threshold
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 80.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Warning" in alert for alert in alerts)

    def test_alert_critical_threshold(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 95.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = None
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Critical" in alert for alert in alerts)

    def test_battery_warning_threshold(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = Mock()
        snapshot.battery.percent = 15.0
        snapshot.battery.power_plugged = False
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Warning" in alert and "Battery" in alert for alert in alerts)

    def test_battery_critical_threshold(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = Mock()
        snapshot.battery.percent = 5.0
        snapshot.battery.power_plugged = False
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert any("Critical" in alert and "Battery" in alert for alert in alerts)

    def test_battery_plugged_no_alert(self, monitor):
        snapshot = Mock(spec=SystemSnapshot)
        snapshot.cpu = Mock()
        snapshot.cpu.percent = 50.0
        snapshot.memory = Mock()
        snapshot.memory.percent = 50.0
        snapshot.disks = []
        snapshot.battery = Mock()
        snapshot.battery.percent = 5.0
        snapshot.battery.power_plugged = True
        snapshot.network = Mock()
        snapshot.network.internet_connected = True

        alerts = monitor._generate_alerts(snapshot)
        assert not any("Battery" in alert for alert in alerts)