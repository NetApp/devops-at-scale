.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. uninstall:

Uninstalling
=================================================

Build-at-Scale can be uninstalled using a single command

    .. code ::

        helm del --purge devops-at-scale

.. note:: Once all the services' PVCs are deleted, Trident deletes the associated PVs and ONTAP volumes
