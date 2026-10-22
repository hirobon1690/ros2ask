from setuptools import find_packages
from setuptools import setup


package_name = 'ros2ask'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hirobon1690',
    maintainer_email='58695125+hirobon1690@users.noreply.github.com',
    description='Execute ROS operations from natural language.',
    license='Apache-2.0',
    entry_points={
        'ros2cli.command': [
            'ask = ros2ask.command:AskCommand',
        ],
    },
)
