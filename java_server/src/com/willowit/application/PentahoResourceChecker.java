package com.willowit.application;

import java.io.IOException;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.Collection;
import java.util.LinkedList;

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PentahoResourceChecker implements Filter {
	
	private static ThreadLocal<Collection<Connection>> connections = new ThreadLocal<Collection<Connection>>() {
		protected java.util.Collection<Connection> initialValue() {
			return new LinkedList<Connection>();
		};
	};

	public static void registerConnection(Connection conn) {
		connections.get().add(conn);
	}
	
	private Logger log;
	
	private FilterConfig config;

	public void init(FilterConfig config) throws ServletException {
		this.config = config;
		this.log = LoggerFactory.getLogger(getClass());
	}

	public void destroy() {
	}

	public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) throws IOException, ServletException {
		Boolean pentaho_boot = (Boolean) config.getServletContext().getAttribute("pentaho_boot_success");

		try {
			if(pentaho_boot != null && pentaho_boot.booleanValue())
				chain.doFilter(req, resp);
			else
				((HttpServletResponse) resp).sendError(404, "Pentaho boot failure!");
		} finally {
			closeAllConnections();
		}
	}

	private void closeAllConnections() {
		for (Connection conn: connections.get()) {
			try {
				if (conn.isClosed()) {
					continue;
				}
				log.warn("Found an open connection after request", conn);
			} catch (SQLException e) {
				log.warn("Failed to check if connection was closed", e);
			}
			try {
				conn.close();
			} catch (SQLException e) {
				log.warn("Failed to close connection", e);
			}
		}
		connections.get().clear();
	}
}
