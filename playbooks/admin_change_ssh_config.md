# Playbook: admin_change_ssh_config

## Description
Change SSHD port and/or root password on target hosts with automatic rollback on failure.
Supports changing port only, password only, or both. Old port is read from inventory.yml automatically.

## tag
`security` `security enforce` `security enforcing` `ssh port` `ssh password`

## Parameters
- new_port (int, optional): New SSHD port number
- root_password (string, optional): New root password. Must be at least 8 characters and contain digits, letters, and special symbols
- host_configs (list, optional): List of host configurations for multi-host with different settings. Format: [{'host': '192.168.1.10', 'new_port': 2222, 'root_password': 'Pass123!'}]

## Input Format (Simplified - single host, same settings)

Use `new_port` and/or `root_password` directly in extravars:

```json
{
  "targets": ["192.168.19.38"],
  "extravars": {
    "new_port": 2222,
    "root_password": "NewP@ss1!"
  }
}
```

## Input Format (Advanced - multi-host, different settings)

Use `host_configs` when different hosts need different settings:

```json
{
  "targets": ["192.168.19.38", "192.168.19.35"],
  "extravars": {
    "host_configs": [
      {"host": "192.168.19.38", "new_port": 3203, "root_password": "Pass1!"},
      {"host": "192.168.19.35", "new_port": 3204, "root_password": "Root2@"}
    ]
  }
}
```

## Use Cases
- Change SSHD port only (pass `new_port` only)
- Change root password only (pass `root_password` only)
- Change both SSHD port and root password (pass both)
- Batch change on multiple hosts with different settings per host

## Execution Flow
1. Validate password strength (if password provided)
2. Backup current sshd_config (timestamped, not overwritten)
3. Remove all existing Port lines and set new port
4. Validate sshd_config syntax (sshd -t) - rollback on failure
5. Reload SSHD service (new and old port listen simultaneously)
6. Wait for new port to start listening
7. Change root password (if password provided)
8. Ping target host to verify connectivity
9. Update local inventory (ORM + inventory.yml) with new port

## Notes
- HIGH-RISK operation: Ensure console access is available as fallback
- At least one of new_port or root_password must be specified
- If root_password is provided, it must be at least 8 characters and contain digits, letters, and special symbols
- Old port is read from inventory.yml automatically
- Password is stored in ORM database only, NOT exported to inventory.yml
- Automatic rollback: If sshd configuration test fails, sshd_config is restored from backup and reloaded
- Each host is processed sequentially (serial: 1)
- Backup file uses timestamped naming to prevent overwrite on repeated runs
