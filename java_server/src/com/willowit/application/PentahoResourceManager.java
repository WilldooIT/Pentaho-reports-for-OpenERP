package com.willowit.application;

import javax.servlet.ServletContextListener;
import javax.servlet.ServletContextEvent;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import org.apache.commons.lang3.exception.ExceptionUtils;

import com.willowit.reporting.PentahoRenderer;

public class PentahoResourceManager implements ServletContextListener {
	private static Log logger = LogFactory.getLog(PentahoResourceManager.class);

	public void contextInitialized(ServletContextEvent event) {
		logger.info("Initialising Pentaho report renderering application.");
		Exception boot_exception = PentahoRenderer.bootPentaho();

		if(boot_exception != null) {
			event.getServletContext().setAttribute("pentaho_boot_success", false);
			logger.error(boot_exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(boot_exception));
		} else
			event.getServletContext().setAttribute("pentaho_boot_success", true);
	}

	public void contextDestroyed(ServletContextEvent event) {
		logger.info("Shutting down Pentaho report renderering application.");
	}
}
