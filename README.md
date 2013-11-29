# Pentaho Reports for OpenERP

This project provides an addon for OpenERP that integrates it with
the Pentaho reporting system. End users of OpenERP can design
reports using Pentaho report designer v5 (instructions on how
to setup the designer: http://bit.ly/L4wPoC), and install/access
them from inside the OpenERP interface.

The second component is a Java based report server designed to be
run as a web application that can be deployed in any standard
Java servlet container (like Tomcat, Jetty, etc.)


## Building the Java component

The included Ant build file contains a "war" target which
performs all the necessary tasks to compile the web application and
create the pentaho-reports-for-openerp.war file. This requires that
Apache Ant be installed, and also Apache Ivy as it is used to retrieve
all the dependencies required to compile and run the application.

	$ cd <extracted_path>/java_server
	$ ant clean
	$ ant war

If the build completed successfully, the WAR file can be found
in the build/jar directory.

For testing purposes, a standalone server that listens on port
8090 (by default) can be launched using the "launch" target:

	$ ant launch


## Integrating and Defining reports to OpenERP

The description of the OpenERP module `pentaho reports` contains an overview
of creating report actions and defining and using report parameters.

## Concurrency issue when using Email Template

When generating a Pentaho report at the same time as parsing the email
template, OpenERP might raises the following exception:

    TransactionRollbackError: could not serialize access due to concurrent
    update

The OpenERP module `willow_pentaho_email_patch` works around this
issue. However, it is not a perfect solution to the problem and we are open
to suggestions and pull requests.

## Contributors

This project was developed by Willow IT, using the libraries and
extensions developed by De Bortoli Wines, Australia (Pieter van der
Merwe in particular) for the Pentaho reporting system. The OpenERP
addon also derives from and/or is inspired by the Jasper Reports addon
developed by NaN-tic.

Willow IT contributions:
	Deepak Seshadri - OpenERP-Pentaho server connector (Java)
	Richard deMeester - frontend and core functions, automated wizard
						and action implementation
	Douglas Parker - additional integration
	Jon Wilson - inspiration, testing, and whipping


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
