Release Notes
================================================================

Release 1.2: Release Notes
--------------------------------------

* DevOps@Scale has been tested and validated to work with ONTAP NFS and iSCSI volumes
* DevOps@Scale now supports deployment in a non-default Kubernetes NameSpace. Namespaces are intended for use in environments with many users spread across multiple teams, or projects
* The solution now supports deployment across multiple storage classes. Each service has a customizable StorageClass field, which when not specified deploys the service with the Kubernetes default storage class
* The solution now supports BitBucket SCM, in addition to GitLab. Please refer to Usage and setup in documentation section for detailed instructions.

Release 1.2: Known Issues
--------------------------------------

* For merge workspace, the new pod is mounting two volumes, one volume with the source workspace and the other volume with a copy of the selected build. The changes have to be merged manually by the developer
* Manual webhook setup for GitLab and Jenkins integration is required for every pipeline
* The CI pipeline build clones are required to be purged manually
* The number of active clones (build and workspace) is limited by ONTAP. Please check the ONTAP release and make sure the purge policies are in place
* The initial BitBucket account should carry the root password that is set by the DevOps@Scale webservice.