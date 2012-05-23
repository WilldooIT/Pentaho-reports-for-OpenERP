# Pentaho Reports for OpenERP

This project provides an addon for OpenERP that integrates it with
the Pentaho reporting system. End users of OpenERP can design 
reports using the Pentaho report designer 3.9 (instructions on how
to setup the designer: http://bit.ly/L4wPoC), and install/access
them from inside the OpenERP interface.

The second component is a Java based report server designed to be
run as a web application that can be deployed in any standard
Java servlet container (like Tomcat, Jetty, etc.)


## Building the Java component

The included Ant build file contains the "war" target which
performs all the necessary tasks to compile the web appliaction and
create the pentaho-reports-for-openerp.war file. This requires that
Apache Ant be installed, and also Apache Ivy as it is used to retrieve
all the dependencies required to compile and run the application.

	$ cd <extracted_path>/java_server
	$ ant war

If the build completed successfully, the WAR file can be found
in the build/jar directory.

For testing purposes, a standalone server that listens on port
8090 (by default) can be launched using the "launch" target:

	$ ant launch


## Contributors

This project was developed by WillowIT, using the libraries and
extensions developed by De Bortoli Wines, Australia (Pieter van der
Merwe in particular) for the Pentaho reporting system. The OpenERP 
addon also derives from and/or is inspired by the Jasper Reports addon
developed by NaN-tic.
