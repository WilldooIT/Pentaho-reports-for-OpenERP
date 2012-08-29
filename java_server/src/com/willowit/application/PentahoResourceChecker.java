package com.willowit.application;

import java.io.IOException;

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletResponse;

public class PentahoResourceChecker implements Filter {
	private FilterConfig config;

	public void init(FilterConfig config) throws ServletException {
		this.config = config;
	}

	public void destroy() {
	}

	public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) throws IOException, ServletException {
		Boolean pentaho_boot = (Boolean) config.getServletContext().getAttribute("pentaho_boot_success");

		if(pentaho_boot != null && pentaho_boot.booleanValue())
			chain.doFilter(req, resp);
		else
			((HttpServletResponse) resp).sendError(404, "Pentaho boot failure!");
	}
}
