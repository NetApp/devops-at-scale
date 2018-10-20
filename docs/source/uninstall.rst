.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. uninstall:

Uninstalling
=================================================

Build-at-Scale can be uninstalled using a single command

	.. code ::

		helm del --purge build-at-scale

.. note :: Deleting the helm deployment does not delete the ontap volumes serving as persistent storage for the various services
