#!/bin/bash
# shellcheck disable=SC1090,SC1091,SC2034,SC2046,SC2086,SC2116,SC2154

export LANG=en_US.UTF-8 &>/dev/null || true
export LC_CTYPE=en_US.UTF-8 &>/dev/null || true
export NLS_LANG=american_america.AL32UTF8 &>/dev/null || true

readonly SETCOLOR_DEBUG="echo -en \\033[1;37m"
readonly SETCOLOR_NORMAL="echo -en \\033[0;39m"
readonly SETCOLOR_SUCCESS="echo -en \\033[1;32m"
readonly SETCOLOR_ERROR="echo -en \\033[1;31m"
readonly SETCOLOR_WARNING="echo -en \\033[1;33m"

script_name=$(basename "$0" 2>/dev/null)
readonly script_name
export TSC_FUNC=1
##################################################
# 向标准 (错误) 输出和指定文件中写入日志
# 所有日志函数返回值都是0, 执行日志函数的结果必为成功. 但是打印到屏幕是分为stdout和stderr的
# 全局变量:
#   log_file
# 参数:
#   日志内容
# 输出:
#   封装后的日志信息
##################################################
function __log() {
    local level="$1"
    shift
    local timestamp line message color_func out_fd
    timestamp=$(date "+%F %T")
    line="${BASH_LINENO[1]:-0}"
    message="$*"
    case "$level" in
    DEBUG)
        ${SETCOLOR_DEBUG}
        out_fd="2"
        ;;
    INFO)
        ${SETCOLOR_NORMAL}
        out_fd="1"
        ;;
    SUCCESS)
        ${SETCOLOR_SUCCESS}
        out_fd="1"
        ;;
    WARNING)
        ${SETCOLOR_WARNING}
        out_fd="2"
        ;;
    ERROR)
        ${SETCOLOR_ERROR}
        out_fd="2"
        ;;
    *)
        ${SETCOLOR_NORMAL}
        out_fd="1"
        ;;
    esac
    {
        printf "%-23s | %-8s | %s:%s - %s\n" \
            "${timestamp}" "${level}" "${script_name}" "${line}" "${message}"
        ${SETCOLOR_NORMAL}
    } | tee -a "${log_file:-/dev/null}" >&"${out_fd}"
    return 0
}

function LOGDEBUG { __log "DEBUG" "$@"; }
function LOGINFO { __log "INFO" "$@"; }
function LOGSUCCESS { __log "SUCCESS" "$@"; }
function LOGWARNING { __log "WARNING" "$@"; }
function LOGERROR { __log "ERROR" "$@"; }
export -f LOGDEBUG LOGINFO LOGSUCCESS LOGWARNING LOGERROR

#######################################
# 删除前导和末尾的空格、制表符、换行符、回车符、全角空格
# Globals:
# Arguments:
#   $1 需要strip的字符串
# Outputs:
#   $1经过strip的值
# Returns:
#   None
#######################################
function str_strip {
    local str="$1"
    echo -n "$str" | sed -E 's/^[[:space:]\xC2\xA0\u3000]+|[[:space:]\xC2\xA0\u3000]+$//g'
}
export -f str_strip

#######################################
# Get the value of a single key under a section from ini file
# Arguments:
#   $1: ini file path
#   $2: section name
#   $3: key name
# Returns:
#   stdout: value (trimmed)
#   exit code:
#     0 - success
#     1 - file missing or empty
#     2 - key not found
#     99 - missing args
#######################################
function get_ini_value() {
    local ini_file="$1"
    local section="$2"
    local key="$3"
    if [[ -z "${ini_file}" || -z "${section}" || -z "${key}" ]]; then
        LOGERROR "Missing arguments in get_ini_value: ini_file=\"${ini_file}\" section=\"${section}\" key=\"${key}\""
        return 99
    fi
    if [[ ! -s "${ini_file}" ]]; then
        LOGERROR "Config file missing or empty: ${ini_file}"
        return 1
    fi
    local value
    value="$(awk -v section="${section}" -v key="${key}" '
        BEGIN {IGNORECASE=1; in_section=0}
        /^\s*\[.*\]\s*$/ {
            in_section = (tolower($0) == "[" tolower(section) "]")
            next
        }
        in_section && $0 ~ "^[[:space:]]*"key"[[:space:]]*=" {
            sub("^[[:space:]]*"key"[[:space:]]*=[[:space:]]*", "", $0)
            gsub(/[[:space:]]+$/, "", $0)
            print $0
            exit
        }
    ' "${ini_file}")"
    if [[ -z "${value}" ]]; then
        LOGERROR "Key \"${key}\" not found in section \"${section}\""
        return 2
    fi
    # LOGDEBUG "get_ini_value: ${section}::${key} = \"${value}\""
    echo "$value"
    return 0
}
export -f get_ini_value

#######################################
# Check if a variable is set, otherwise try to read from ini config file
# Arguments:
#   $1: ini file path
#   $2: section name
#   $3: variable name
# Returns:
#   0 - variable exists or loaded successfully
#   3 - variable not set and not found in config
#######################################
function get_var() {
    local ini_file="$1"
    local section="$2"
    local var_name="$3"
    local var_value="${!var_name:-}"
    if [[ -z "$var_value" ]]; then
        # LOGDEBUG "Variable \$${var_name} unset, trying to load from ${ini_file} [${section}]"
        local val
        val="$(get_ini_value "${ini_file}" "${section}" "${var_name}")" || return $?
        declare -g "${var_name}"="${val}"
        var_value="${val}"
    fi
    if [[ -z "${var_value}" ]]; then
        LOGERROR "Variable \$${var_name} unset and not found in config (${ini_file} [${section}])"
        return 3
    fi
    return 0
}
export -f get_var

#######################################
# 版本号比较, gt lt eq ge le
# Arguments:
#   $1 需比较的版本号 如1.1.1q
#   $2 需比较的版本号 如1.1.1t
# Outputs:
#   None
# Returns:
#   true/false
#######################################
function version_gt() {
    local v1="$1" v2="$2"
    [[ "$(printf '%s\n' "${v1}" "${v2}" | sort -V | head -n1)" != "${v1}" ]]
}
function version_lt() {
    local v1="$1" v2="$2"
    [[ "$(printf '%s\n' "${v1}" "${v2}" | sort -rV | head -n1)" != "${v1}" ]]
}
function version_eq() {
    [[ "$1" == "$2" ]]
}
function version_ge() {
    version_gt "$1" "$2" || version_eq "$1" "$2"
}
function version_le() {
    version_lt "$1" "$2" || version_eq "$1" "$2"
}
export -f version_gt version_lt version_eq version_ge version_le

##################################################
# 开启 xtrace 调试模式
# 全局变量:
#   DEBUG
# 参数:
#   "$@" (脚本级别位置变量 $@)
##################################################
function debug {
    if [[ "$(eval echo "\${$#}")" != "debug" ]]; then
        DEBUG=false
        return 0
    fi
    DEBUG=true
    # PS4='+ { \033[1;32m${LINENO} \033[1;34m${FUNCNAME[0]}\033[0m } '
    PS4='+ ${LINENO} ${FUNCNAME[0]}: '
    set -x
}
export -f debug

##################################################
# 当用户中止执行时, 调用此函数输出提示信息, 脚本退出
# 参数:
#   None
# 输出:
#   脚本中止的提示信息
##################################################
function gracefully_abort {
    echo -en "\033[1;0m"
    LOGWARNING "用户中止执行，脚本退出"
    exit 1
}
export -f gracefully_abort

##################################################
# 尝试优雅地中止进程及其子进程, 若等待时间内未成功中止, 则进行暴力中止
# 参数:
#   PID
#   用于优雅中止的信号量 (可选参数, 默认 15|TERM)
#   优雅中止等待时间 (可选参数, 默认 30 秒.
#     合法的单位有: s|m|h|d. 无单位默认 s. 支持小数)
# 输出:
#   遇到错误则将错误信息输出到 stderr
# 返回:
#   遇到错误则 exit 1
##################################################
function proc_killer {
    if [[ "$1" =~ ^[0-9]+$ ]]; then
        local -r pid="$1"
    else
        LOGERROR "${FUNCNAME[0]}: PID 参数不合法: $1"
        return 1
    fi

    local sig="TERM"
    [[ -n "$2" ]] && sig="$2"

    local term_grace_duration="30s"
    [[ -n "$3" ]] && term_grace_duration="$3"
    term_grace_duration="$(_conv2sec "$term_grace_duration")" || {
        LOGERROR "${FUNCNAME[0]}: 优雅中止时间格式错误: $3"
        return 1
    }

    if kill -0 "${pid}" &>/dev/null; then
        kill -"${sig}" "${pid}" &>/dev/null
        sig="KILL"

        local timer=0.0
        local -r step=0.2
        while sleep "$step"; do
            kill -0 "${pid}" &>/dev/null || break
            timer=$(awk -v a="$timer" -v b="$step" 'BEGIN {printf "%.4f", a+b}')
            if [[ "$(awk -v a="$timer" -v b="$term_grace_duration" 'BEGIN {print (a>b)?1:0}')" == 1 ]]; then
                kill -"${sig}" "${pid}" &>/dev/null
                break
            fi
        done
    fi
}
export -f proc_killer

##################################################
# 将形如 1m, 1h, 1d 的时间转换为相应秒数
# 参数:
#   时间字串 (合法的单位有: s|m|h|d. 无单位默认 s. 支持小数, 例如 0.15h)
# 输出:
#   纯数字 (秒数)
# 返回:
#   遇到错误则 return 1
##################################################
function _conv2sec {
    local input="$1"
    local number unit result

    if [[ -z "$input" ]]; then
        LOGERROR "_conv2sec: 缺少参数"
        return 1
    fi

    # 使用正则提取数字和单位（兼容小数）
    if [[ "$input" =~ ^([0-9]+(\.[0-9]+)?)([smhdSMHD]?)$ ]]; then
        number="${BASH_REMATCH[1]}"
        unit=$(echo "$unit" | tr '[:upper:]' '[:lower:]')
        case "$unit" in
        "") result="$number" ;; # 默认为秒
        "s") result="$number" ;;
        "m") result=$(awk "BEGIN {printf \"%.4f\", $number * 60}") ;;
        "h") result=$(awk "BEGIN {printf \"%.4f\", $number * 3600}") ;;
        "d") result=$(awk "BEGIN {printf \"%.4f\", $number * 86400}") ;;
        *)
            LOGERROR "_conv2sec: 不支持的时间单位: $unit"
            return 1
            ;;
        esac
        echo "$result"
        return 0
    else
        LOGERROR "_conv2sec: 非法时间格式: $input"
        return 1
    fi
}
export -f _conv2sec

##################################################
# 简版 timeout 命令, 用法: tmout DURATION COMMAND
# 参数:
#   持续时间 (支持小数. 合法的单位有: s|m|h|d. 无单位默认 s)
#   执行的命令
# 输出:
#   遇到错误则将错误信息输出到 stderr
# 返回:
#   遇到错误则 exit 1, 超时 return 124
##################################################
function tmout {
    (($# < 2)) && LOGERROR "${FUNCNAME[0]}: 参数不足 (\$*: $*)" && return 1

    local duration
    duration="$(_conv2sec "$1")" || {
        LOGERROR "${FUNCNAME[0]}: 时间转换失败: $1"
        return 1
    }
    shift 1
    local cmd=("$@")

    "${cmd[@]}" &
    local pid="$!"

    if [[ -z "${pid}" ]]; then
        LOGERROR "${FUNCNAME[0]}: 子进程执行失败"
        return 1
    fi

    local timer=0.0
    local -r step=0.2
    while sleep "$step"; do
        timer=$(awk -v a="$timer" -v b="$step" 'BEGIN {printf "%.4f", a+b}')
        [[ "$(awk -v a="$timer" -v b="$duration" 'BEGIN {print (a>b)?1:0}')" == 1 ]] && break
        kill -0 "$pid" &>/dev/null || break
    done

    proc_killer "$pid" "SIGTERM" "10s" # 默认优雅终止等待时间

    wait "$pid" 2>/dev/null
    local ret=$?
    ((ret > 128)) && ret=124
    return "$ret"
}
export -f tmout

#################################### cc=79 ####################################
# 转换 syslog 日志的时间为绝对秒, 该函数为样例不合适直接使用, 实际使用建议加跳出条件
# 注意若日志跨年, 需要在此函数做额外处理, 本函数默认都把时间处理为今年
# 参数:
#   $1: syslog 输出的日志名
# 输出:
#   将 syslog 日志的时间格式转换为绝对秒后的日志
# 返回:
#   遇到错误则 exit 1
#################################### cc=79 ####################################
function convert_syslog_timestamp {
    local syslog_file=$1
    if [[ -f ${syslog_file} ]]; then
        awk '{
            month = substr($0, 1, 3)
            day = substr($0, 5, 2)
            time = substr($0, 8, 8)
            cmd = "date -d \""month " " day " "time" \" +\"%s\""
            cmd |getline timestamp
            close(cmd)
            print timestamp,$0
        }' "${syslog_file}"
    else
        LOGERROR "日志文件不存在: ${syslog_file}"
        return 1
    fi
}

#################################### cc=79 ####################################
# 判断给定的 IP 是否在给定的网段内.
# 参数:
#   $1: 需判断是否在网段内的 IP
#   $2: 用来确定网段的IP/MASK(192.168.1.0/24)
#   $3: 可选, 如 $2 是 IP 形式, 则这里写四位掩码形式(255.255.255.252)
# 输出:
#   IP是否在网段内
# 返回:
#   0: 是
#   1: 否
#   2: 参数不合法
#################################### cc=79 ####################################
function is_ip_in_network() {
    local ip="$1"
    local netmask="$2" # 支持 CIDR 或 网络地址
    local mask="$3"    # 可选，掩码（255.255.255.0）

    if [[ -z "$ip" ]] || [[ -z "$netmask" ]]; then
        return 2
    fi
    awk -v ip="$ip" -v netmask="$netmask" -v mask="$mask" '
    function ip2int(ipstr,    n, a, i, ipint) {
        n = split(ipstr, a, ".")
        if (n != 4) return -1
        ipint = 0
        for (i=1; i<=4; i++) {
            if (a[i] !~ /^[0-9]+$/ || a[i] < 0 || a[i] > 255) return -1
            ipint = ipint * 256 + a[i]
        }
        return ipint
    }
    function cidr2mask(cidr,    maskint, bits) {
        bits = cidr
        if (bits < 0 || bits > 32) return -1
        maskint = 0
        for (i=0; i<32; i++) {
            maskint = maskint * 2 + (i < bits ? 1 : 0)
        }
        return maskint
    }
    BEGIN {
        ipint = ip2int(ip)
        if (ipint == -1) exit 2

        split(netmask, parts, "/")
        if (length(parts) == 2) {
            netip = parts[1]
            cidr = parts[2] + 0
            maskint = cidr2mask(cidr)
            if (maskint == -1) exit 2
        } else if (mask != "") {
            netip = netmask
            maskint = ip2int(mask)
            if (maskint == -1) exit 2
        } else {
            exit 2
        }

        netipint = ip2int(netip)
        if (netipint == -1) exit 2

        if ((ipint & maskint) == (netipint & maskint)) {
            exit 0
        } else {
            exit 1
        }
    }
    '
    return $?
}
export -f is_ip_in_network

##################################################
# 检测系统信息，包括发行版、版本、内核、架构等
# 并判断该机器是虚拟机 (VM) 还是物理机 (PM)
# 全局变量:
#   None
# 参数:
#   None
# 输出:
#   JSON 格式的系统信息
# 返回:
#   0 - 成功
#   1 - Bash 版本过低或缺少 jq 工具
##################################################
function detect_system_info() {
    if ((BASH_VERSINFO[0] < 4)); then
        LOGERROR "Bash version too low, requires at least 4.0"
        return 1
    fi

    command -v jq &>/dev/null ||
        {
            LOGERROR "jq command not found, please install jq to use this function"
            return 1
        }

    local -A DISTRO_VARIETY_MAP=(
        [ubuntu]="Debian"
        [debian]="Debian"
        [linuxmint]="Debian"
        [centos]="RedHat"
        [rhel]="RedHat"
        [fedora]="RedHat"
        [rocky]="RedHat"
        [almalinux]="RedHat"
        [kylin]="RedHat"
        [neokylin]="RedHat"
        [arch]="Arch"
        [manjaro]="Arch"
        [alpine]="Alpine"
        [suse]="Suse"
        [opensuse]="Suse"
        [fitserveros]="Euler"
        [fitstarryskyos]="Euler"
        [openeuler]="Euler"
        [hce]="Euler"
        [ningos]="Euler"
    )

    [[ -f /etc/os-release ]] && source /etc/os-release

    local distribution distribution_version distribution_release distribution_file_path os_kernel machine_architecture distribution_major_version
    distribution="${NAME:-unknown}"
    distribution_version="${VERSION_ID:-unknown}"
    distribution_release="${VERSION:-unknown}"
    distribution_file_path="/etc/os-release"
    os_kernel="$(uname -r)"
    machine_architecture="$(uname -m)"
    distribution_major_version="$(echo "$distribution_version" | cut -d. -f1)"

    local ids=()
    [[ -n "$ID" ]] && ids+=("$ID")
    IFS=' ' read -ra id_likes <<<"${ID_LIKE:-}"
    ids+=("${id_likes[@]}")

    local distribution_file_variety="unknown" id_lc
    for id in "${ids[@]}"; do
        id_lc="$(echo "$id" | tr '[:upper:]' '[:lower:]')"
        if [[ -n "${DISTRO_VARIETY_MAP[$id_lc]}" ]]; then
            distribution_file_variety="${DISTRO_VARIETY_MAP[$id_lc]}"
            break
        fi
    done

    local pkg_mgr="unknown"
    if command -v apt &>/dev/null; then
        pkg_mgr="apt"
    elif command -v dnf &>/dev/null; then
        pkg_mgr="dnf"
    elif command -v yum &>/dev/null; then
        pkg_mgr="yum"
    elif command -v zypper &>/dev/null; then
        pkg_mgr="zypper"
    elif command -v pacman &>/dev/null; then
        pkg_mgr="pacman"
    elif command -v apk &>/dev/null; then
        pkg_mgr="apk"
    fi

    local service_mgr="unknown"
    if pidof systemd &>/dev/null; then
        service_mgr="systemd"
    elif command -v rc-service &>/dev/null; then
        service_mgr="openrc"
    elif command -v sv &>/dev/null; then
        service_mgr="runit"
    fi

    local machine_type="pm"
    local vm_product_name_patterns="${VM_PRODUCT_NAME_PATTERNS:-virtualbox|vmware|kvm|qemu|openstack|xen|bochs|bhyve|parallels|xen|hyper-v|cloud|google|amazon|digital|huawei|nutanix|oracle|aliyun|tencent|ucloud|aws|azure|gcp}"
    local product_name="unknown" product_name_lc

    if [[ -f /sys/class/dmi/id/product_name ]]; then
        product_name="$(</sys/class/dmi/id/product_name)"
        product_name_lc="$(echo "$product_name" | tr '[:upper:]' '[:lower:]')"
        if [[ "$product_name_lc" =~ $vm_product_name_patterns ]]; then
            machine_type="vm"
        fi
    elif [[ -f /proc/cpuinfo ]]; then
        if grep -qiE "hypervisor|vmware|kvm" /proc/cpuinfo; then
            machine_type="vm"
        fi
    fi

    jq -n \
        --arg os_distribution "$distribution" \
        --arg os_pkg_mgr "$pkg_mgr" \
        --arg os_distribution_file_path "$distribution_file_path" \
        --arg os_distribution_file_variety "$distribution_file_variety" \
        --arg os_kernel "$os_kernel" \
        --arg machine_architecture "$machine_architecture" \
        --arg os_distribution_major_version "$distribution_major_version" \
        --arg os_distribution_version "$distribution_version" \
        --arg os_distribution_release "$distribution_release" \
        --arg os_service_mgr "$service_mgr" \
        --arg machine_type "$machine_type" \
        --arg product_name "$product_name" \
        '{
            os_distribution: $os_distribution,
            os_pkg_mgr: $os_pkg_mgr,
            os_distribution_file_path: $os_distribution_file_path,
            os_distribution_file_variety: $os_distribution_file_variety,
            os_kernel: $os_kernel,
            machine_architecture: $machine_architecture,
            os_distribution_major_version: $os_distribution_major_version,
            os_distribution_version: $os_distribution_version,
            os_distribution_release: $os_distribution_release,
            os_service_mgr: $os_service_mgr,
            machine_type: $machine_type,
                        product_name: $product_name
        }'
}
export -f detect_system_info

##################################################
# 备份指定目录，并使用时间戳作为后缀进行轮询备份
# 支持自动清理旧备份 (保留最多 N 个)
# 函数会在执行前检查并临时启用 extglob，执行后恢复原状态
# 全局变量:
#   None
# 参数:
#   $1 - 要备份的目标目录路径 (必填)
#   $2 - 最多保留的备份数量 (可选，默认为5)
# 输出:
#   标准输出显示操作信息
# 返回:
#   0 - 成功
#   1 - 参数缺失或目标目录不存在
#   2 - 备份失败 (如 mv 失败)
##################################################
backup_dir_with_rotation() {
    local target_dir="$1"
    local max_backups="${2:-5}"
    local base backup_root bak_prefix new_backup timestamp
    if [[ -z "${target_dir}" ]]; then
        LOGERROR "Target directory must be provided as the first argument."
        return 1
    fi
    if [[ ! -e "${target_dir}" ]]; then
        return 0
    fi
    base="$(basename "${target_dir}")"
    backup_root="$(dirname "${target_dir}")"
    bak_prefix="${backup_root}/${base}.bak"

    timestamp=$(date "+%Y%m%d%H%M%S")
    new_backup="${bak_prefix}.${timestamp}"
    if mv "${target_dir}" "${new_backup}"; then
        LOGSUCCESS "Backup: '${target_dir}' -> '${new_backup}'"
    else
        LOGERROR "Backup: '${target_dir}' -> '${new_backup}'"
        return 2
    fi
    local timestamp_pattern='[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
    # mapfile -d '' old_backups < <(
    #     find "${backup_root}" -maxdepth 1 -type d \
    #         -name "${base}.bak.${timestamp_pattern}" \
    #         -print0 2>/dev/null |
    #         sort -z
    # )
    local old_backups=()
    while IFS= read -r -d '' line; do
        old_backups+=("$line")
    done < <(
        find "${backup_root}" -maxdepth 1 -type d \
            -name "${base}.bak.${timestamp_pattern}" \
            -print0 2>/dev/null |
            sort -z
    )
    if [[ "${#old_backups[@]}" -ne 0 ]]; then
        local count remove_count
        count="${#old_backups[@]}"
        remove_count="$((count - max_backups))"
        if ((remove_count > 0)); then
            for ((i = 0; i < remove_count; i++)); do
                rm -rf "${old_backups[i]}"
            done
        fi
    fi
}
export -f backup_dir_with_rotation