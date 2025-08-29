"""Test container setup and Docker availability."""

import pytest
import docker
from docker.errors import DockerException, ImageNotFound


def test_docker_daemon_available() -> None:
    """Verify Docker daemon is running and accessible."""
    try:
        client = docker.from_env()
        ping_result = client.ping()
        assert ping_result is True, "Docker daemon not responding"
        print("✓ Docker daemon is running and accessible")
    except DockerException as e:
        pytest.fail(f"Docker is not available: {e}")


def test_required_images_available() -> None:
    """Verify required container images are available or can be pulled."""
    client = docker.from_env()

    required_images = ["redis:7-alpine", "rabbitmq:3.12-management-alpine"]

    for image_name in required_images:
        try:
            # Check if image exists locally
            image = client.images.get(image_name)
            print(f"✓ Image {image_name} is available locally (ID: {image.short_id})")
        except ImageNotFound:
            # Try to pull the image
            print(f"⟳ Image {image_name} not found locally, pulling...")
            try:
                image = client.images.pull(image_name)
                print(f"✓ Successfully pulled {image_name}")
            except Exception as e:
                pytest.fail(f"Failed to pull image {image_name}: {e}")


def test_no_conflicting_containers() -> None:
    """Check for any conflicting containers that might interfere with tests."""
    client = docker.from_env()

    # Look for any existing test containers
    containers = client.containers.list(all=True)
    test_containers = [c for c in containers if "testcontainers" in c.name]

    if test_containers:
        print(f"⚠ Found {len(test_containers)} existing test container(s)")
        for container in test_containers:
            print(f"  - {container.name} ({container.status})")
            if container.status == "running":
                print(f"    Stopping {container.name}...")
                container.stop()
                container.remove()
                print(f"    ✓ Removed {container.name}")
    else:
        print("✓ No conflicting test containers found")


def test_port_availability() -> None:
    """Check if commonly used ports are available."""
    import socket

    # Ports that might be used by test containers
    # These are dynamic, but we check common defaults
    common_ports = [
        (6379, "Redis"),
        (5672, "RabbitMQ AMQP"),
        (15672, "RabbitMQ Management"),
    ]

    for port, service in common_ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", port))
        sock.close()

        if result == 0:
            print(f"⚠ Port {port} ({service}) is in use - tests will use dynamic ports")
        else:
            print(f"✓ Port {port} ({service}) is available")


def test_docker_network() -> None:
    """Verify Docker networking is functional."""
    client = docker.from_env()

    # Check if bridge network exists and is functional
    networks = client.networks.list()
    bridge_network = None

    for network in networks:
        if network.name == "bridge":
            bridge_network = network
            break

    assert bridge_network is not None, "Docker bridge network not found"

    # Check network details
    network_info = bridge_network.attrs
    assert network_info["Driver"] == "bridge", "Bridge network driver incorrect"
    print(
        f"✓ Docker bridge network is available (subnet: {network_info.get('IPAM', {}).get('Config', [{}])[0].get('Subnet', 'N/A')})"
    )


def test_container_runtime() -> None:
    """Test that we can create and destroy a simple container."""
    client = docker.from_env()

    try:
        # Run a simple alpine container
        container = client.containers.run(
            "alpine:latest",
            "echo 'test'",
            detach=True,
            remove=False,
            name="test_container_runtime_check",
        )

        # Wait for it to complete
        result = container.wait()
        assert (
            result["StatusCode"] == 0
        ), f"Container exited with non-zero status: {result['StatusCode']}"

        # Check output
        logs = container.logs().decode("utf-8").strip()
        assert logs == "test", f"Unexpected output: {logs}"

        # Clean up
        container.remove()

        print("✓ Can successfully create and run containers")

    except Exception as e:
        pytest.fail(f"Failed to run test container: {e}")
    finally:
        # Ensure cleanup
        try:
            container = client.containers.get("test_container_runtime_check")
            container.remove(force=True)
        except Exception:
            pass  # Container already removed or doesn't exist
