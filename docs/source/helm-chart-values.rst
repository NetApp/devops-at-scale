   
Sample helm chart parameters  
==========================================

	Build-At-Scale master helm chart is combination of various components and the following page describes all the available options for each helm component.
	
	i) CouchDB:-
		Build-At-Scale uses couchDB to maintain internal state of various objects and build information. This couchDB instance runs as a kubernetes pod and is setup via helm chart. To have persistent storage attached for the couchDB pod we can specify ontap values in the couchDB helm chart.
		
		
		
	=======================       ======       ===============================================================================================
	Parameter                     Value        Description                                                                                    
	=======================       ======       ===============================================================================================
	volume                        true         Name of the volume to be created for couchDB pod                                              
	volumeSize                                 Size of the volume to be created for couchDB pod                                              
	volumeMountPath                            Junction path of the volume created for couchDB pod                                            
	volumeUID                                  UID for the volume created                                                                        
	volumeGID                                  GID for the volume created                                                                      
	=======================       ======       ===============================================================================================
	

	ii) Gitlab:-
		Build-At-Scale deploys gitlab by deafult as an SCM tool. Gitlab is deployed as a kubernetes pod on Netapp storage.
		
		
		
	=======================       ================       ===============================================================================================
	Parameter                     Value                  Description                                                                                    
	=======================       ================       ===============================================================================================
	volume                        true                   Name of the volume to be created for gitlab pod                                              
	volumeSize                                           Size of the volume to be created for gitlab pod                                              
	volumeMountPath                                      Junction path of the volume created for couchDB pod                                            
	volumeUID                                            UID for the volume created                                                                        
	volumeGID                                            GID for the volume created                                                                      
	=======================       ================       ===============================================================================================
	
	
	
	