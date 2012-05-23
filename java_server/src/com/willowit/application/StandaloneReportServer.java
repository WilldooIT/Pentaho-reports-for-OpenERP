package com.willowit.application;

import org.apache.xmlrpc.server.XmlRpcServer;
import org.apache.xmlrpc.server.PropertyHandlerMapping;
import org.apache.xmlrpc.webserver.WebServer;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import com.willowit.reporting.PentahoRenderer;

public class StandaloneReportServer {
	private static Log logger = LogFactory.getLog(StandaloneReportServer.class);

	public static void main(String[] args) {
		//Start up Pentaho
		Exception boot_exception = PentahoRenderer.bootPentaho();
		if(boot_exception != null) {
			logger.error(boot_exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(boot_exception));
			System.exit(1);
		}

		try {
			int port = 8090;

			if(args.length > 0)
				port = java.lang.Integer.parseInt(args[0]);

			java.net.InetAddress server_spec = java.net.Inet4Address.getByName("0.0.0.0");

			logger.info("Attempting to start XML-RPC server at " + server_spec.toString() + ":" + port);
			WebServer server = new WebServer(port, server_spec);
			XmlRpcServer rpc_server = server.getXmlRpcServer();

			PropertyHandlerMapping phm = new PropertyHandlerMapping();
			phm.addHandler("report", PentahoRenderer.class);
			rpc_server.setHandlerMapping(phm);

			server.start();
			logger.info("Started successfully");
			logger.info("Accepting requests");
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));
		}
	}
}
