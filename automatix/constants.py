CONSTANTS = {
    'apt_update':  'apt-get -qy update',
    'apt_upgrade': 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends upgrade',
    'apt_full_upgrade': 'DEBIAN_FRONTEND=noninteractive apt-get -qy -o Dpkg::Options::=--force-confold --no-install-recommends full-upgrade',
}
