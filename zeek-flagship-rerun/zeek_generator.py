#!/usr/bin/env python3
"""
Zeek conn.log Generator for Benchmark Testing

Generates realistic Zeek network connection logs with configurable parameters
for performance benchmarking of Splunk DB Connect vs alternatives.
"""

import json
import csv
import random
import time
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse
import pyarrow as pa
import pyarrow.parquet as pq
from faker import Faker
import numpy as np

class ZeekGenerator:
    """Generate realistic Zeek conn.log data"""

    def __init__(self, seed: int = 42):
        """Initialize generator with seed for reproducibility"""
        random.seed(seed)
        np.random.seed(seed)
        self.fake = Faker()
        Faker.seed(seed)

        # Network configuration
        self.internal_subnets = [
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16')
        ]

        # Pre-generate IP pools for performance
        self.internal_ips = self._generate_internal_ips(15000)
        self.external_ips = self._generate_external_ips(250000)

        # Service and port mappings
        self.services = {
            'http': 80,
            'ssl': 443,
            'ssh': 22,
            'dns': 53,
            'smtp': 25,
            'ftp': 21,
            'rdp': 3389,
            'smb': 445,
            'ntp': 123,
            'snmp': 161
        }

        # Connection states (Zeek format)
        self.conn_states = [
            'SF',  # Normal connection close
            'S1',  # Connection attempt seen, no reply
            'REJ', # Connection rejected
            'S0',  # Connection attempt, no reply
            'RSTO', # Connection reset by originator
            'RSTR', # Connection reset by responder
            'SH',  # Originator sent SYN then FIN
            'SHR', # Responder sent SYN then FIN
            'OTH'  # No SYN seen
        ]

        # Protocols
        self.protocols = ['tcp', 'udp', 'icmp']

        # Traffic distribution (realistic enterprise)
        self.traffic_dist = {
            'web': 0.70,      # HTTP/HTTPS traffic
            'dns': 0.15,      # DNS queries
            'admin': 0.10,    # SSH/RDP
            'other': 0.05     # Everything else
        }

    def _generate_internal_ips(self, count: int) -> List[str]:
        """Generate pool of internal IP addresses"""
        ips = []
        for _ in range(count):
            subnet = random.choice(self.internal_subnets)
            # Generate random host within subnet
            host_bits = 32 - subnet.prefixlen
            host_int = random.randint(1, (2 ** host_bits) - 2)
            ip = subnet.network_address + host_int
            ips.append(str(ip))
        return list(set(ips))  # Remove any duplicates

    def _generate_external_ips(self, count: int) -> List[str]:
        """Generate pool of external IP addresses"""
        ips = []
        for _ in range(count):
            # Generate public IPs (avoid private ranges)
            while True:
                ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
                ip_obj = ipaddress.ip_address(ip)
                if not ip_obj.is_private and not ip_obj.is_multicast and not ip_obj.is_reserved:
                    ips.append(ip)
                    break
        return list(set(ips))

    def _generate_uid(self) -> str:
        """Generate Zeek-style unique connection ID"""
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        return 'C' + ''.join(random.choices(chars, k=17))

    def _select_traffic_type(self) -> str:
        """Select traffic type based on distribution"""
        r = random.random()
        cumulative = 0
        for traffic_type, prob in self.traffic_dist.items():
            cumulative += prob
            if r <= cumulative:
                return traffic_type
        return 'other'

    def generate_connection(self, base_timestamp: float) -> Dict:
        """Generate a single Zeek connection record"""

        # Determine traffic type and set parameters accordingly
        traffic_type = self._select_traffic_type()

        if traffic_type == 'web':
            service = random.choice(['http', 'ssl'])
            resp_port = self.services[service]
            proto = 'tcp'
            # Web traffic typically has more received bytes
            orig_bytes = random.randint(100, 5000)
            resp_bytes = random.randint(1000, 500000)
            duration = random.uniform(0.01, 30.0)
            conn_state = random.choices(['SF', 'S1', 'REJ'], weights=[0.9, 0.05, 0.05])[0]

        elif traffic_type == 'dns':
            service = 'dns'
            resp_port = 53
            proto = random.choice(['udp', 'tcp'])
            orig_bytes = random.randint(20, 200)
            resp_bytes = random.randint(50, 500)
            duration = random.uniform(0.001, 0.1)
            conn_state = 'SF' if proto == 'udp' else random.choice(['SF', 'S1'])

        elif traffic_type == 'admin':
            service = random.choice(['ssh', 'rdp'])
            resp_port = self.services[service]
            proto = 'tcp'
            orig_bytes = random.randint(1000, 50000)
            resp_bytes = random.randint(1000, 50000)
            duration = random.uniform(1.0, 3600.0)  # Long-lived connections
            conn_state = random.choices(['SF', 'S1'], weights=[0.95, 0.05])[0]

        else:  # other
            service = random.choice(list(self.services.keys()))
            resp_port = self.services[service]
            proto = random.choice(self.protocols)
            orig_bytes = random.randint(0, 10000)
            resp_bytes = random.randint(0, 10000)
            duration = random.uniform(0.0, 60.0)
            conn_state = random.choice(self.conn_states)

        # Determine if internal->external or internal->internal
        if random.random() < 0.8:  # 80% internal to external
            orig_h = random.choice(self.internal_ips)
            resp_h = random.choice(self.external_ips)
        else:  # 20% internal to internal
            orig_h = random.choice(self.internal_ips)
            resp_h = random.choice(self.internal_ips)

        # Generate source port (ephemeral range)
        orig_port = random.randint(1024, 65535)

        # Calculate packet counts (rough approximation)
        avg_packet_size = 500  # bytes
        orig_pkts = max(1, orig_bytes // avg_packet_size)
        resp_pkts = max(1, resp_bytes // avg_packet_size)

        # Build connection record
        conn = {
            'ts': base_timestamp + random.uniform(0, 1),
            'uid': self._generate_uid(),
            'id.orig_h': orig_h,
            'id.orig_p': orig_port,
            'id.resp_h': resp_h,
            'id.resp_p': resp_port,
            'proto': proto,
            'service': service if random.random() < 0.7 else None,  # 30% unidentified
            'duration': duration if conn_state == 'SF' else 0,
            'orig_bytes': orig_bytes,
            'resp_bytes': resp_bytes,
            'conn_state': conn_state,
            'missed_bytes': 0 if random.random() < 0.99 else random.randint(1, 1000),
            'history': self._generate_history(conn_state),
            'orig_pkts': orig_pkts,
            'resp_pkts': resp_pkts,
            'tunnel_parents': []
        }

        return conn

    def _generate_history(self, conn_state: str) -> str:
        """Generate connection history string based on state"""
        if conn_state == 'SF':
            return random.choice(['ShADadFf', 'ShADadfF', 'ShAdDaFf'])
        elif conn_state == 'S1':
            return 'S'
        elif conn_state == 'REJ':
            return 'Sr'
        else:
            return random.choice(['S', 'Sh', 'ShA', 'ShAD'])

    def generate_batch(self, size: int = 1000000, start_time: Optional[datetime] = None) -> List[Dict]:
        """Generate batch of Zeek connection records"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=1)

        base_ts = start_time.timestamp()
        connections = []

        # Generate connections with time progression
        time_increment = 3600.0 / size  # Spread over an hour

        for i in range(size):
            ts = base_ts + (i * time_increment)
            conn = self.generate_connection(ts)
            connections.append(conn)

        return connections

    def save_json(self, connections: List[Dict], filename: str):
        """Save connections to JSON file"""
        with open(filename, 'w') as f:
            for conn in connections:
                json.dump(conn, f)
                f.write('\n')

    def save_csv(self, connections: List[Dict], filename: str):
        """Save connections to CSV file"""
        if not connections:
            return

        fieldnames = connections[0].keys()
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(connections)

    def save_parquet(self, connections: List[Dict], filename: str):
        """Save connections to Parquet file"""
        # Convert to pandas-like structure for PyArrow
        data = {key: [conn[key] for conn in connections] for key in connections[0].keys()}

        # Define schema
        schema = pa.schema([
            ('ts', pa.float64()),
            ('uid', pa.string()),
            ('id.orig_h', pa.string()),
            ('id.orig_p', pa.int32()),
            ('id.resp_h', pa.string()),
            ('id.resp_p', pa.int32()),
            ('proto', pa.string()),
            ('service', pa.string()),
            ('duration', pa.float64()),
            ('orig_bytes', pa.int64()),
            ('resp_bytes', pa.int64()),
            ('conn_state', pa.string()),
            ('missed_bytes', pa.int64()),
            ('history', pa.string()),
            ('orig_pkts', pa.int64()),
            ('resp_pkts', pa.int64()),
            ('tunnel_parents', pa.list_(pa.string()))
        ])

        # Create table
        table = pa.Table.from_pydict(data, schema=schema)

        # Write Parquet file with compression
        pq.write_table(table, filename, compression='snappy')


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Generate Zeek conn.log data for benchmarking')
    parser.add_argument('--rows', type=int, default=1000000,
                       help='Number of connection records to generate')
    parser.add_argument('--batch-size', type=int, default=1000000,
                       help='Batch size for generation (for memory efficiency)')
    parser.add_argument('--output-dir', type=str, default='../../data/samples',
                       help='Output directory for generated files')
    parser.add_argument('--formats', nargs='+', default=['json', 'csv', 'parquet'],
                       choices=['json', 'csv', 'parquet'],
                       help='Output formats to generate')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')

    args = parser.parse_args()

    # Initialize generator
    print(f"Initializing Zeek generator with seed {args.seed}")
    generator = ZeekGenerator(seed=args.seed)

    # Generate data in batches
    total_generated = 0
    batch_num = 0
    all_connections = []

    print(f"Generating {args.rows:,} Zeek connection records...")

    while total_generated < args.rows:
        batch_size = min(args.batch_size, args.rows - total_generated)

        # Generate batch
        print(f"  Generating batch {batch_num + 1} ({batch_size:,} records)...")
        connections = generator.generate_batch(batch_size)
        all_connections.extend(connections)

        total_generated += batch_size
        batch_num += 1

        # Print sample record
        if batch_num == 1:
            print("\nSample record:")
            print(json.dumps(connections[0], indent=2))

    # Save to different formats
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for fmt in args.formats:
        filename = f"{args.output_dir}/zeek_conn_{args.rows}_{timestamp}.{fmt}"
        print(f"\nSaving to {fmt} format: {filename}")

        if fmt == 'json':
            generator.save_json(all_connections, filename)
        elif fmt == 'csv':
            generator.save_csv(all_connections, filename)
        elif fmt == 'parquet':
            generator.save_parquet(all_connections, filename)

    print(f"\n✅ Successfully generated {total_generated:,} Zeek connection records")

    # Print statistics
    total_bytes = sum(c['orig_bytes'] + c['resp_bytes'] for c in all_connections)
    print(f"\nDataset Statistics:")
    print(f"  Total connections: {len(all_connections):,}")
    print(f"  Total bytes: {total_bytes:,} ({total_bytes / 1e9:.2f} GB)")
    print(f"  Unique internal IPs: {len(set(c['id.orig_h'] for c in all_connections)):,}")
    print(f"  Unique external IPs: {len(set(c['id.resp_h'] for c in all_connections if not ipaddress.ip_address(c['id.resp_h']).is_private)):,}")


if __name__ == '__main__':
    main()