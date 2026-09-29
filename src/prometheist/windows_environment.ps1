param([int]$MaxRows, [int]$CimTimeoutSeconds)
# Local read-only queries. No web request, discovery broadcast, pairing, device
# command, Phone Link database access, location, microphone or camera capture.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Emit-Section([string]$Name, [scriptblock]$Body) {
    try {
        $rows = @(& $Body)
        $status = if ($rows.Count -gt $MaxRows) { 'PARTIAL' } else { 'COMPLETE' }
        $record = @{ provider=$Name; status=$status; rows=@($rows | Select-Object -First $MaxRows) }
    } catch {
        $record = @{ provider=$Name; status='ERROR'; rows=@(); diagnostic=$_.Exception.Message }
    }
    ConvertTo-Json -InputObject $record -Depth 12 -Compress
}
function Cim([string]$Class, [string]$Namespace='root/cimv2') {
    Get-CimInstance -Namespace $Namespace -ClassName $Class -OperationTimeoutSec $CimTimeoutSeconds
}

Emit-Section 'windows.system' {
    Cim 'Win32_ComputerSystem' | Select-Object Name,Manufacturer,Model,SystemType,NumberOfProcessors,NumberOfLogicalProcessors,TotalPhysicalMemory
}
Emit-Section 'windows.cpu' {
    Cim 'Win32_Processor' | Select-Object DeviceID,Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,Architecture,VirtualizationFirmwareEnabled
}
Emit-Section 'windows.memory' {
    Cim 'Win32_PhysicalMemory' | Select-Object DeviceLocator,BankLabel,Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,SMBIOSMemoryType,FormFactor
}
Emit-Section 'windows.gpu' {
    Cim 'Win32_VideoController' | Select-Object DeviceID,PNPDeviceID,Name,AdapterRAM,DriverVersion,VideoProcessor,Status,ConfigManagerErrorCode
}
Emit-Section 'windows.disks' {
    Cim 'Win32_DiskDrive' | Select-Object DeviceID,PNPDeviceID,Model,InterfaceType,Size,MediaType,Status,Partitions
}
Emit-Section 'windows.storage' {
    Get-PhysicalDisk | ForEach-Object {
        @{ DeviceId=[string]$_.DeviceId; FriendlyName=$_.FriendlyName; Size=$_.Size;
           BusType=[string]$_.BusType; MediaType=[string]$_.MediaType;
           HealthStatus=[string]$_.HealthStatus; OperationalStatus=@($_.OperationalStatus | ForEach-Object {[string]$_}) }
    }
}
Emit-Section 'windows.ports' {
    Cim 'Win32_PortConnector' | Select-Object Tag,InternalReferenceDesignator,ExternalReferenceDesignator,PortType,ConnectorType
}
Emit-Section 'windows.displays' {
    Cim 'WmiMonitorConnectionParams' 'root/wmi' | Select-Object InstanceName,Active,VideoOutputTechnology
}
Emit-Section 'windows.pnp' {
    $devices = @(Get-PnpDevice -PresentOnly)
    $parents = @{}
    # Parent lookup is optional. Failure is reported on every affected node; it
    # does not convert a successfully enumerated present device to an absence.
    $parentStatus = 'COMPLETE'
    try {
        if ($devices.Count) {
            Get-PnpDeviceProperty -InstanceId @($devices.InstanceId) -KeyName 'DEVPKEY_Device_Parent' |
                ForEach-Object { $parents[$_.InstanceId] = $_.Data }
        }
    } catch { $parentStatus = 'UNAVAILABLE' }
    foreach ($device in $devices) {
        @{ InstanceId=$device.InstanceId; FriendlyName=$device.FriendlyName; Class=$device.Class;
           Status=[string]$device.Status; Problem=[string]$device.Problem;
           Parent=$parents[$device.InstanceId]; ParentLookup=$parentStatus;
           Inspection='HOST_EXPOSED_INTERFACES_ONLY' }
    }
}
Emit-Section 'windows.network' {
    Get-NetAdapter -IncludeHidden | ForEach-Object {
        @{ InterfaceGuid=[string]$_.InterfaceGuid; Name=$_.Name; InterfaceDescription=$_.InterfaceDescription;
           Status=[string]$_.Status; LinkSpeed=[string]$_.LinkSpeed;
           PhysicalMediaType=[string]$_.PhysicalMediaType; HardwareInterface=$_.HardwareInterface;
           Virtual=$_.Virtual; ConnectorPresent=$_.ConnectorPresent; ifIndex=$_.ifIndex }
    }
}
Emit-Section 'windows.connectivity' {
    Get-NetConnectionProfile | ForEach-Object {
        @{ InterfaceIndex=$_.InterfaceIndex; InterfaceAlias=$_.InterfaceAlias;
           IPv4Connectivity=[string]$_.IPv4Connectivity; IPv6Connectivity=[string]$_.IPv6Connectivity;
           Evidence='OS_REPORTED'; ActiveProbeByPrometheist=$false }
    }
}
Emit-Section 'windows.battery' {
    Cim 'Win32_Battery' | Select-Object DeviceID,Name,Status,Chemistry,DesignVoltage,DesignCapacity,FullChargeCapacity,EstimatedChargeRemaining,BatteryStatus
}
Emit-Section 'windows.thermal' {
    Cim 'MSAcpi_ThermalZoneTemperature' 'root/wmi' | Select-Object InstanceName,CurrentTemperature
}
Emit-Section 'windows.phone_link' {
    $packages = @(Get-AppxPackage -Name 'Microsoft.YourPhone') + @(Get-AppxPackage -Name 'MicrosoftWindows.CrossDevice')
    $running = @(Get-Process -Name 'PhoneExperienceHost','CrossDeviceService' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName -Unique)
    foreach ($package in $packages) {
        @{ Name=$package.Name; Version=[string]$package.Version; RunningProcesses=$running;
           PhoneConnection='UNKNOWN'; SensorAccess='NOT_ESTABLISHED'; MicrosoftAccountQueried=$false }
    }
}

Emit-Section 'windows.security.privileges' {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    @{ Name='Current process'; Elevated=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);
       AutoElevation=$false }
}
Emit-Section 'windows.security.firewall' {
    Get-NetFirewallProfile -PolicyStore ActiveStore | ForEach-Object {
        @{ Name=[string]$_.Name; Enabled=[string]$_.Enabled;
           DefaultInboundAction=[string]$_.DefaultInboundAction; DefaultOutboundAction=[string]$_.DefaultOutboundAction;
           AllowLocalFirewallRules=[string]$_.AllowLocalFirewallRules }
    }
    Get-NetFirewallRule -PolicyStore ActiveStore | Where-Object { $_.Group -eq 'Prometheist local privacy v1' } | ForEach-Object {
        @{ Name=$_.Name; Enabled=[string]$_.Enabled; Direction=[string]$_.Direction; Action=[string]$_.Action;
           Program=@($_ | Get-NetFirewallApplicationFilter | Select-Object -ExpandProperty Program);
           RemoteAddress=@($_ | Get-NetFirewallAddressFilter | Select-Object -ExpandProperty RemoteAddress) }
    }
}
Emit-Section 'windows.security.defender' {
    $state = Get-MpComputerStatus
    @{ Name='Microsoft Defender'; AMServiceEnabled=$state.AMServiceEnabled; AntivirusEnabled=$state.AntivirusEnabled;
       AntispywareEnabled=$state.AntispywareEnabled; BehaviorMonitorEnabled=$state.BehaviorMonitorEnabled;
       IoavProtectionEnabled=$state.IoavProtectionEnabled; NISEnabled=$state.NISEnabled;
       OnAccessProtectionEnabled=$state.OnAccessProtectionEnabled; RealTimeProtectionEnabled=$state.RealTimeProtectionEnabled;
       IsTamperProtected=$state.IsTamperProtected; DefenderSignaturesOutOfDate=$state.DefenderSignaturesOutOfDate;
       AntivirusSignatureVersion=$state.AntivirusSignatureVersion; AMRunningMode=$state.AMRunningMode }
}
Emit-Section 'windows.security.tpm' {
    $state = Get-Tpm
    @{ Name='TPM'; Present=$state.TpmPresent; Ready=$state.TpmReady; Enabled=$state.TpmEnabled;
       Activated=$state.TpmActivated; LockedOut=$state.LockedOut }
}
Emit-Section 'windows.security.secure_boot' {
    @{ Name='UEFI Secure Boot'; Enabled=(Confirm-SecureBootUEFI) }
}
Emit-Section 'windows.security.encryption' {
    # Only status properties. Never enumerate KeyProtector / recovery passwords.
    Get-BitLockerVolume | ForEach-Object {
        @{ Name=$_.MountPoint; VolumeStatus=[string]$_.VolumeStatus; ProtectionStatus=[string]$_.ProtectionStatus;
           EncryptionMethod=[string]$_.EncryptionMethod; EncryptionPercentage=$_.EncryptionPercentage;
           LockStatus=[string]$_.LockStatus }
    }
}

# Default readable physical sensors. All additional sensor devices remain in
# windows.pnp even if no supported reading API exists for them. GetDefault does
# not prompt for camera/mic/location permissions or start content capture.
$sensorDefinitions = @{
    Accelerometer=@('AccelerationX','AccelerationY','AccelerationZ');
    Gyrometer=@('AngularVelocityX','AngularVelocityY','AngularVelocityZ');
    Compass=@('HeadingMagneticNorth','HeadingTrueNorth');
    Inclinometer=@('PitchDegrees','RollDegrees','YawDegrees');
    LightSensor=@('IlluminanceInLux');
    Barometer=@('StationPressureInHectopascals')
}
foreach ($sensorName in @($sensorDefinitions.Keys | Sort-Object)) {
    Emit-Section "windows.sensor.$sensorName" {
        # Only the application-owned class names above enter this expression.
        $type = [Type]::GetType("Windows.Devices.Sensors.$sensorName, Windows.Devices.Sensors, ContentType=WindowsRuntime", $true)
        $sensor = $type.GetMethod('GetDefault', [Type[]]@()).Invoke($null, @())
        if ($null -ne $sensor) {
            $reading = $sensor.GetCurrentReading()
            $values = @{}
            if ($null -ne $reading) {
                foreach ($property in $sensorDefinitions[$sensorName]) {
                    if ($null -ne $reading.$property) { $values[$property] = [double]$reading.$property }
                }
            }
            @{ DeviceId=$sensor.DeviceId; Name=$sensorName; ReadingAvailable=($null -ne $reading); Values=$values }
        }
    }
}
