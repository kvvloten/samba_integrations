################
# WLAN Manager #
################
$script_path = Split-Path -Parent $MyInvocation.MyCommand.Definition
$reg_values = @("DhcpDefaultGateway", "DhcpDomain", "DhcpDomainSearchList", "DhcpGatewayHardware", "DhcpGatewayHardwareCount", 
                "DhcpInterfaceOptions", "DhcpIPAddress", "DhcpNameServer", "DhcpServer", "DhcpSubnetMask", "DhcpSubnetMaskOpt",
                "Lease", "LeaseObtainedTime", "LeaseTerminatesTime", "T1", "T2")
$nic_regpath = "HKLM:\SYSTEM\ControlSet001\Services\Tcpip\Parameters\Interfaces"


Function Configure-DomainWLAN
{
    Try
    {
        $domain_wlan_profile = "$script_path\wlan_profile.xml"
        $domain_wlan_name = ([xml](Get-Content $domain_wlan_profile)).WLANProfile.name
        Write-Host "Domain-WLAN: '$domain_wlan_name'"
        
        Write-Host "Import (add or update) Domain-WLAN profile: '$domain_wlan_name'"
        netsh wlan add profile filename="$domain_wlan_profile" user=all
        $xml = [xml](Get-Content $domain_wlan_profile)
        $ssid = $xml.WLANProfile.SSIDConfig.SSID.name
        netsh wlan set profileparameter name=$ssid connectionmode=auto
    }
    Catch {Continue}
}


Function Disable-WLANAdapters
{
    $nics = Get-NetAdapter -name "Wi-Fi*"
    ForEach ($nic in $nics)
    {
        $nic_name = $nic.Name
        Write-Host "Disable WLAN '$nic_name'"
        $mac = $nic.MacAddress.Replace("-", ":")
        $nic_wmi = (Get-WmiObject -Class Win32_NetworkAdapterConfiguration | Where-Object {$_.MACAddress -eq $mac})
        If ($nic_wmi -ne $null)
        {
            $nic_wmi.ReleaseDHCPLease() | Out-Null
            $uuid = $nic_wmi.SettingID
            Write-Host "Remove DHCP-settings for WLAN nic '$mac' with uuid '$uuid'"
            ForEach ($value in $values) {Remove-ItemProperty -Path "$nic_regpath\$uuid" -Name "$value" -ErrorAction SilentlyContinue}
        }
        Disable-NetAdapter -Name $nic_name -IncludeHidden -Confirm:$False
    }
}


Function Enable-WLANAdapters
{
    $nics = Get-NetAdapter -name "Ethernet*"
    ForEach ($nic in $nics)
    {
        $nic_name = $nic.Name
        Write-Host "Deconfigure LAN '$nic_name'"
        $mac = $nic.MacAddress.Replace("-", ":")
        $uuid = (Get-WmiObject -Class Win32_NetworkAdapterConfiguration | Where-Object {$_.MACAddress -eq $mac}).SettingID
        Write-Host "Remove DHCP-settings for LAN nic '$mac' with uuid '$uuid'"
        ForEach ($value in $values) {Remove-ItemProperty -Path "$nic_regpath\$uuid" -Name "$value" -ErrorAction SilentlyContinue}
        Disable-NetAdapter -Name $nic_name -IncludeHidden -Confirm:$False
        Enable-NetAdapter -Name $nic_name -IncludeHidden -Confirm:$False
    }
    $nics = Get-NetAdapter -name "Wi-Fi*"
    ForEach ($nic in $nics)
    {
        $nic_name = $nic.Name
        Write-Host "Enable WLAN '$nic_name'"
        Enable-NetAdapter -Name $nic_name -IncludeHidden -Confirm:$False
        Configure-DomainWLAN
    }
}


Function Test-WiredConnection
{
    $connected = $false
    $nics = Get-NetAdapter -name "Ethernet*"
    ForEach ($nic in $nics)
    {
        $nic_name = $nic.Name
        $nic_status = $nic.Status
        $connected = $connected -or ($nic_status -eq "Up")
        # Write-Host "Tested '$nic_name' with '$nic_status', new connection-state '$connected'"
    }
    Return $connected
}


Function Test-WirelessEnabled 
{
    $enabled = $false
    $nics = Get-NetAdapter -name "Wi-Fi*"
    ForEach ($nic in $nics)
    {
        $nic_name = $nic.Name
        $nic_status = $nic.Status
        $enabled = $enabled -or ("Up", "Disconnected").contains($nic_status)
    }
    Return $enabled
}


## Main 
While ($true)
{
    $wired_connection = Test-WiredConnection
    $wireless_enabled = Test-WirelessEnabled
    # Write-Host "ETH: $wired_connection WLAN: $wireless_enabled"
    If ($wired_connection -eq $true -and $wireless_enabled -eq $true)
    {
        Write-Host ""
        Write-Host "Wired connection detected, disabling Wireless connection... " -ForegroundColor Yellow
        Disable-WLANAdapters
        Write-Host "Wait until wireless connection is disabled" -ForegroundColor White -BackgroundColor Green
        While ((Test-WiredConnection) -eq $true -and (Test-WirelessEnabled) -eq $true)
        {
            Sleep -Seconds 1
            Write-Host "."  -NoNewline -ForegroundColor White -BackgroundColor Green
        }
        Write-Host "Done" -ForegroundColor White -BackgroundColor Green
    }

    ElseIf ($wired_connection -eq $false -and $wireless_enabled -eq $false)
    {
        Write-Host ""
        Write-Host "Wired connection lost, enabling Wireless connection... " -ForegroundColor Yellow
        Enable-WLANAdapters
        Write-Host "Wait until wireless connection is enabled" -ForegroundColor White -BackgroundColor Green
        While ((Test-WiredConnection) -eq $false -and (Test-WirelessEnabled) -eq $false)
        {
            Sleep -Seconds 1
            Write-Host "."  -NoNewline -ForegroundColor White -BackgroundColor Green
        }
        Write-Host "Done" -ForegroundColor White -BackgroundColor Green
    }
    Else
    {
        Write-Host "."  -NoNewline -ForegroundColor Yellow
        Sleep -Seconds 1
    }
}
