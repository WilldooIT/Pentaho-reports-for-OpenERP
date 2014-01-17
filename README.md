# Pentaho Reports for OpenERP

This project provides a system that integrates OpenERP with
the Pentaho reporting system. End users of OpenERP can design
reports using Pentaho report designer v5.0, and install/access
them from inside the OpenERP interface. 

### Features:
* Support for OpenERP 6.1 and 7.0.
* OpenERP data can be accessed via SQL, Objects, custom python procedures, or via "Pentaho Data Integration" tools.
* Report parameters specified in the designer are automatically prompted for when he report is run from OpenERP.
* Parameters can be generated dynamically from various data sources. 

_Pentaho Report designer_ is the software separate from this project that is used to design the report templates. You can download the designer [here](http://sourceforge.net/projects/pentaho/files/Report%20Designer/).

We have prepared a number of instructional videos for the designer [here](https://www.youtube.com/user/WillowITMedia). Keep in mind that while these videos are for version 3.9 of the designer, they are still applicable. 

## A note about about versions

At the time of writing, this project was working with version 3.9.1 of the Pentaho report designer, however this version is no longer supported and may stop working at any time. If you wish to use version 3.9.1, please follow the [instructions](http://pvandermpentaho.blogspot.com.au/2012/05/adding-openerp-datasource-to-pentaho.html) to install the required plugin for the report designer. 

Version 5.0 is the latest version of the report designer, and does not require the above steps, as it comes bundled with all required plugins (data sources etc).

## Overview

This project encompasses two separate components:

### The Java component

This is a Java web application that can be deployed in a suitable container such as [Apache Tomcat](http://tomcat.apache.org/). This component does the actual rendering of the reports based upon the definitions created in the [Pentaho Report Designer](http://sourceforge.net/projects/pentaho/files/Report%20Designer/), which is separate from this project. The Java Server communicates with OpenERP to retrieve the required data, and works with the OpenERP module (described below) to prompt the user for any required parameters, and provide selections for these parameters.

### The OpenERP Module

The other component in this project is the OpenERP Module. This module allows OpenERP to communicate with the Java Server to render reports created with the Report Designer. For a more detailed explanation, look at the description of the module in OpenERP, or [Here](https://github.com/WillowIT/Pentaho-reports-for-OpenERP/blob/version70/openerp_addon/pentaho_reports/__openerp__.py). 

## Quick Start:

Once you have designed and created your reports using the [Pentaho Report Designer](http://sourceforge.net/projects/pentaho/files/Report%20Designer/) (which is software that is separate from this project), you will need to install the report server and the install the module for OpenERP. The quickest and easiest way to do this is to download a pre-built .war file from [here](http://cloud1.willowit.com.au/dist/pentaho-reports-for-openerp.war). Keep in mind that although this file will be rebuilt and updated on a semi-regular basis, if you require the latest, bleeding edge version, you will have to build it yourself following the instructions [below.](#building-and-installing) 

Once you have the war file, you will need an application container such as [Apache Tomcat](http://tomcat.apache.org/) for it to run in. Installation and deployment on Tomcat or any other application container is beyond the scope of this document, however the tomcat website has very detailed documentation on how to do so. 

The next step is to install and configure the openerp module, which is explained [here](#the-openerp-module-1). 

Finally, you will need to deploy your reports. Instructions for doing this can be found in the [module description](https://github.com/WillowIT/Pentaho-reports-for-OpenERP/blob/version70/openerp_addon/pentaho_reports/__openerp__.py) under the "Report Actions" heading. 



## Building and Installing

### The Java Server
To build the Java server component, you will need a suitable [Java Development Kit](http://www.oracle.com/technetwork/java/javase/downloads/jdk7-downloads-1880260.html) installed on your system. 
Additionally, you will need to install and configure [Apache Ant](http://ant.apache.org/) and [Apache Ivy](http://ant.apache.org/ivy/). Ant is the build system, and Ivy downloads all of the required dependencies required when building this component.

Ant uses a build file to define the steps required when building a Java project. The included Ant build file contains a "war" target which performs all the necessary tasks to compile the web application and
create the pentaho-reports-for-openerp.war file. 

	$ cd <extracted_path>/java_server
	$ ant clean
	$ ant war

If the build completed successfully, the WAR file can be found
in the dist directory.

For testing purposes, a standalone server that listens on port
8090 (by default) can be launched using the "launch" target:

	$ ant launch

For production deployment, however, it is recommended that the server be hosted in an application container. Instructions on how to deploy the war file on tomcat can be found [here](http://tomcat.apache.org/tomcat-6.0-doc/deployer-howto.html#Deploying_using_the_Tomcat_Manager).

### The OpenERP module

This module is installed like any other OpenERP module. Briefly:

* Place the 'openerp_addon' folder somewhere on your filesystem that is accessible to your openerp server.
* Update your openerp-server.conf file, and include the full path to this folder on the addons_path line.
* Restart OpenERP and login as Administrator
* Go to Settings -> Update Modules List and click Update
* Click Installed Modules and search for 'pentaho'
* Install the "Pentaho reports for OpenERP" module. 

Once this has been completed, you will still need configure the module. Refer to the [module description](https://github.com/WillowIT/Pentaho-reports-for-OpenERP/blob/version70/openerp_addon/pentaho_reports/__openerp__.py) for detailed instructions on how to do this. 



## Appendices

### Integrating and Defining reports to OpenERP

The description of the OpenERP module `pentaho reports` contains an overview
of creating report actions and defining and using report parameters.

### Concurrency issue when using Email Template

When generating a Pentaho report at the same time as parsing the email
template, OpenERP might raises the following exception:

    TransactionRollbackError: could not serialize access due to concurrent
    update

The OpenERP module `willow_pentaho_email_patch` works around this
issue. However, it is not a perfect solution to the problem and we are open
to suggestions and pull requests.

### Contributors

This project was developed by Willow IT, using the libraries and
extensions developed by De Bortoli Wines, Australia (Pieter van der
Merwe in particular) for the Pentaho reporting system. The OpenERP
addon also derives from and/or is inspired by the Jasper Reports addon
developed by NaN-tic.

Willow IT contributions:

* Deepak Seshadri - OpenERP-Pentaho server connector (Java)
* Richard deMeester - frontend and core functions, automated wizard and action implementation
* Douglas Parker - additional integration
* Jon Wilson - inspiration, testing, and whipping
* Thomas Cook - Documentation

## Disclaimer

This has been developed over time to meet specific requirements as we have
needed to meet them. If something is wrong, or you think would make a great
feature, please do let us know at:

	support@willowit.com.au


## Report Library

We will be endeavouring to create a library of sample and useful reports.
Check at:

	http://www.willowit.com.au/

where we will announce when and where this is available. In the meantime, if
you develop any reports or templates that you would consider worth sharing,
please email them through with some description or details.
