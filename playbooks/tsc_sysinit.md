# Playbook: tsc_sysinit

## Description
System Initialization Configuration. Configure system to a standard initialization status including SELinux, Firewall, Timezone, Systemd services, Sshd service, system_parameter, and fhmv.

## Parameters
- ntp_server (string, optional): ntpd server ip. Optional, do not pass if not needed.

## Use Cases
- Configure system to a standard initialization status
- Including SELinux, Firewall, Timezone, Systemd services, Sshd service, system_parameter, and fhmv
- You can specify ntp server

## Example
```json
{
  "targets": ["192.168.1.10"],
  "extravars": {
    "ntp_server": "192.168.1.100"
  }
}
```

## Notes
- Requires tsc_tools to be installed on target hosts
- Source profile: /home/tsc/tsc_profile
- Execute command if given ntp server: tsc --tsc_sysinit --all --ntp_server 192.168.1.100
- Execute command if no extravars given: tsc --tsc_sysinit --all
- IMPORTANT: Do NOT pass default values in extravars. Only pass parameters when user explicitly specifies them.
