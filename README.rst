===============================================
Tempest Integration of swift_multiregion_replication
===============================================

Most of this project is boilerplate needed for a tempest plugin.

Edit tests/swift_nodes_credentials.json with SSH login credentials for
the swift nodes you want to test.

##Usage

Run
````
pip install .
````
to register this as a Tempest plugin

Alternatively, tests/test_multiregion_replication.py can be run like any other python unittest
