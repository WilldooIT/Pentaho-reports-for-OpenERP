package com.willowit.reporting;

import java.util.HashMap;
import java.util.Hashtable;
import java.util.ArrayList;
import java.util.Enumeration;

import java.io.StringWriter;
import java.io.PrintWriter;
import java.io.ByteArrayOutputStream;

import org.apache.xmlrpc.server.XmlRpcServer;
import org.apache.xmlrpc.server.XmlRpcServerConfigImpl;
import org.apache.xmlrpc.server.PropertyHandlerMapping;
import org.apache.xmlrpc.webserver.WebServer;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import org.pentaho.reporting.engine.classic.core.AbstractReportDefinition;
import org.pentaho.reporting.engine.classic.core.ClassicEngineBoot;
import org.pentaho.reporting.engine.classic.core.CompoundDataFactory;
import org.pentaho.reporting.engine.classic.core.DataFactory;
import org.pentaho.reporting.engine.classic.core.ReportElement;
import org.pentaho.reporting.engine.classic.core.MasterReport;
import org.pentaho.reporting.engine.classic.core.Section;

import org.pentaho.reporting.engine.classic.core.modules.output.table.csv.CSVReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.rtf.RTFReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.html.HtmlReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.xls.ExcelReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.pdf.PdfReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.plaintext.PlainTextReportUtil;

import org.pentaho.reporting.engine.classic.core.modules.misc.datafactory.sql.SQLReportDataFactory;
import org.pentaho.reporting.engine.classic.core.modules.misc.datafactory.sql.DriverConnectionProvider;

import org.pentaho.reporting.engine.classic.core.parameters.ReportParameterDefinition;
import org.pentaho.reporting.engine.classic.core.parameters.ParameterDefinitionEntry;
import org.pentaho.reporting.engine.classic.core.parameters.DefaultParameterContext;
import org.pentaho.reporting.engine.classic.core.parameters.ReportParameterValidator;
import org.pentaho.reporting.engine.classic.core.parameters.ValidationResult;
import org.pentaho.reporting.engine.classic.core.parameters.ValidationMessage;

import org.pentaho.reporting.engine.classic.core.util.ReportParameterValues;

import org.pentaho.reporting.libraries.fonts.LibFontBoot;
import org.pentaho.reporting.libraries.resourceloader.LibLoaderBoot;
import org.pentaho.reporting.libraries.resourceloader.Resource;
import org.pentaho.reporting.libraries.resourceloader.ResourceManager;

import org.pentaho.reporting.engine.classic.extensions.datasources.openerp.OpenERPDataFactory;
import com.debortoliwines.openerp.reporting.di.OpenERPFilterInfo;

public class ReportServer {
	private static Log logger = LogFactory.getLog(ReportServer.class);

	//One common manager instance to be initialised on startup
	private static ResourceManager manager;

	//Unique for every invocation
	private String openerp_host = null;
	private String openerp_port = null;
	private String openerp_db = null;
	private String openerp_login = null;
	private String openerp_password = null;

	private String postgres_host = null;
	private String postgres_port = null;
	private String postgres_db = null;
	private String postgres_login = null;
	private String postgres_password = null;

	private String output_type = "pdf";
	private Object parameter_ids = null;
	private HashMap<String, Object> parameters = new HashMap<String, Object>();
	private byte[] prpt_file_content = null;
	
	public ArrayList<HashMap> getParameterInfo(Hashtable args) throws Exception {
		ArrayList<HashMap> ret_val = new ArrayList<HashMap>();

		try {
			prpt_file_content = (byte[]) args.get("_prpt_file_content");

			//Load the report (we may be overriding Pentaho's caching mechanisms by doing this
			Resource res = manager.createDirectly(prpt_file_content, MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();

			//New stuff
			ReportParameterDefinition param_def = report.getParameterDefinition();
			ParameterDefinitionEntry[] param_def_entries = param_def.getParameterDefinitions();
			DefaultParameterContext param_context = new DefaultParameterContext(report);
			for(ParameterDefinitionEntry param_def_entry : param_def_entries) {
				HashMap<String, Object> one_param_info = new HashMap<String, Object>();
				HashMap<String, Object> zero_namespace_attributes = new HashMap<String, Object>();

				one_param_info.put("name", param_def_entry.getName());
				one_param_info.put("value_type", param_def_entry.getValueType().getName());
				one_param_info.put("is_mandatory", param_def_entry.isMandatory());

				Object default_value = param_def_entry.getDefaultValue(param_context);
				if(default_value != null) {
					String param_def_entry_type = param_def_entry.getValueType().getName();

					if(param_def_entry_type.equals("java.lang.Long"))
						default_value = ((Long) default_value).intValue();
					else if(param_def_entry_type.equals("java.lang.Short"))
						default_value = ((java.lang.Short) default_value).intValue();
					else if(param_def_entry_type.equals("java.math.BigInteger"))
						default_value = ((java.math.BigInteger) default_value).intValue();
					else if(param_def_entry_type.equals("java.lang.Number"))
						default_value = ((Number) default_value).doubleValue();
					else if(param_def_entry_type.equals("java.lang.Float"))
						default_value = ((Float) default_value).doubleValue();
					else if(param_def_entry_type.equals("java.math.BigDecimal"))
						default_value = ((java.math.BigDecimal) default_value).doubleValue();

					one_param_info.put("default_value", default_value);
				}
				one_param_info.put("attributes", zero_namespace_attributes);

				String[] param_attr_nss = param_def_entry.getParameterAttributeNamespaces();
				for(String param_attr_ns : param_attr_nss)
					logger.debug("Attribute namespace: " + param_attr_ns);

				String[] param_attr_names = param_def_entry.getParameterAttributeNames(param_attr_nss[0]);
				for(String param_attr_name : param_attr_names) {
					String param_attr = param_def_entry.getParameterAttribute(param_attr_nss[0], param_attr_name, param_context);
					zero_namespace_attributes.put(param_attr_name, param_attr);
					logger.debug("Attribute: " + param_attr_name + " = " + param_attr);
				}

				ret_val.add(one_param_info);
			}

			return ret_val;
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));
			throw exception;
		}
	}

	private HashMap<String, Object> getParametersTypes(MasterReport report) throws Exception {
		ReportParameterDefinition param_def = report.getParameterDefinition();
		ParameterDefinitionEntry[] param_def_entries = param_def.getParameterDefinitions();
		DefaultParameterContext param_context = new DefaultParameterContext(report);

		HashMap<String, Object> name_to_type = new HashMap<String, Object>();

		for(ParameterDefinitionEntry param_def_entry : param_def_entries)
			name_to_type.put(param_def_entry.getName(), param_def_entry.getValueType());

		return name_to_type;
	}

	public byte[] execute(Hashtable args) throws Exception {
		try {
			for(Enumeration argnames = args.keys(); argnames.hasMoreElements();) {
				String argname = (String) argnames.nextElement();
				Object argval = args.get(argname); 
				logger.debug(argname + ": " + argval);
				if(argname.equals("_openerp_host"))
					openerp_host = (String) argval;
				else if (argname.equals("_openerp_port"))
					openerp_port = (String) argval;
				else if (argname.equals("_openerp_db"))
					openerp_db = (String) argval;
				else if (argname.equals("_openerp_login"))
					openerp_login = (String) argval;
				else if (argname.equals("_openerp_password"))
					openerp_password = (String) argval;
				else if(argname.equals("_postgres_host"))
					postgres_host = (String) argval;
				else if (argname.equals("_postgres_port"))
					postgres_port = (String) argval;
				else if (argname.equals("_postgres_db"))
					postgres_db = (String) argval;
				else if (argname.equals("_postgres_login"))
					postgres_login = (String) argval;
				else if (argname.equals("_postgres_password"))
					postgres_password = (String) argval;
				else if (argname.equals("_prpt_file_content"))
					prpt_file_content = (byte[]) argval;
				else if (argname.equals("_output_type"))
					output_type = (String) argval;
				else if (argname.equals("ids"))
					parameter_ids = argval;
				else parameters.put(argname, argval);
			}

			//Load the report (we may be overriding Pentaho's caching mechanisms by doing this
			Resource res = manager.createDirectly(prpt_file_content, MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();
			HashMap<String, Object> parameters_types = getParametersTypes(report);

			//Fix up data sources specified by parameters passed in
			fixConfiguration(report);

			//Pass through other parameters
			ReportParameterValues values = report.getParameterValues();
			for(String parameter_name : parameters.keySet()) {
				Object parameter_value = parameters.get(parameter_name);
				if(parameters_types.get(parameter_name) != null) {
					String parameter_type = ((Class) parameters_types.get(parameter_name)).getName();
					if(parameter_type.equals("java.lang.Long"))
						values.put(parameter_name, new Long(((Integer) parameter_value)));
					else if(parameter_type.equals("java.lang.Short"))
						values.put(parameter_name, ((Integer) parameter_value).shortValue());
					else if(parameter_type.equals("java.math.BigInteger"))
						values.put(parameter_name, java.math.BigInteger.valueOf(((Integer) parameter_value)));
					else if(parameter_type.equals("java.lang.Float"))
						values.put(parameter_name, ((Double) parameter_value).floatValue());
					else if(parameter_type.equals("java.math.BigDecimal"))
						values.put(parameter_name, java.math.BigDecimal.valueOf(((Double) parameter_value)));
					else if(parameter_type.equals("java.sql.Date"))
						values.put(parameter_name, new java.sql.Date(((java.util.Date) parameter_value).getTime()));
					else if(parameter_type.equals("java.sql.Time"))
						values.put(parameter_name, new java.sql.Time(((java.util.Date) parameter_value).getTime()));
					else if(parameter_type.equals("java.sql.Timestamp"))
						values.put(parameter_name, new java.sql.Timestamp(((java.util.Date) parameter_value).getTime()));
					else
						values.put(parameter_name, parameter_value);
				}
			}

			//Create the report output stream
			ByteArrayOutputStream report_bin_out = new ByteArrayOutputStream();
			if(output_type.equals("pdf"))
				PdfReportUtil.createPDF(report, report_bin_out);
			else if(output_type.equals("xls"))
				ExcelReportUtil.createXLS(report, report_bin_out);
			else if(output_type.equals("csv"))
				CSVReportUtil.createCSV(report, report_bin_out, null);
			else if(output_type.equals("rtf"))
				RTFReportUtil.createRTF(report, report_bin_out);
			else if(output_type.equals("html"))
				HtmlReportUtil.createStreamHTML(report, report_bin_out);
			else if(output_type.equals("txt"))
				PlainTextReportUtil.createPlainText(report, report_bin_out);

			return report_bin_out.toByteArray();
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));
			throw exception;
		}
	}

	public static void main(String[] args) {
		//Start up Pentaho
		if(ClassicEngineBoot.getInstance().isBootDone() == false) {
			LibLoaderBoot.getInstance().start();
			LibFontBoot.getInstance().start();
			ClassicEngineBoot.getInstance().start();

			Exception exception = ClassicEngineBoot.getInstance().getBootFailureReason();
			if (exception != null) {
				StringWriter trace_stream = new StringWriter();
				exception.printStackTrace(new PrintWriter(trace_stream));

				logger.error(exception.getMessage());
				logger.error(trace_stream.toString());

				System.exit(1);
			}
		}
		manager = new ResourceManager();
		manager.registerDefaults();

		try {
			int port = 8090;

			if(args.length > 0)
				port = java.lang.Integer.parseInt(args[0]);

			java.net.InetAddress server_spec = java.net.Inet4Address.getByName("0.0.0.0");

			logger.info("Attempting to start XML-RPC server at " + server_spec.toString() + ":" + port);
			WebServer server = new WebServer(port, server_spec);
			XmlRpcServer rpc_server = server.getXmlRpcServer();

			PropertyHandlerMapping phm = new PropertyHandlerMapping();
			phm.addHandler("report", ReportServer.class);
			rpc_server.setHandlerMapping(phm);

			//XmlRpcServerConfigImpl server_config = (XmlRpcServerConfigImpl) rpc_server.getConfig();
			//server_config.setEnabledForExtensions(true);

			server.start();
			logger.info("Started successfully");
			logger.info("Accepting requests");
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));
		}
	}

	//DBW
	private void fixConfiguration(Section section) throws Exception {
		//If one of the datasources is an OpenERP datasource, reset the connection to the passed parameters
		if(section instanceof AbstractReportDefinition) {
			String selected_query_name = ((AbstractReportDefinition) section).getQuery();

			CompoundDataFactory factories = (CompoundDataFactory) ((AbstractReportDefinition) section).getDataFactory();
			for(int j = 0; j < factories.size(); j++) {
				DataFactory data_factory = factories.getReference(j);
				if(data_factory instanceof OpenERPDataFactory) {
					OpenERPDataFactory factory = (OpenERPDataFactory) data_factory;

					//Fix up connection parameters
					if(openerp_host != null)
						factory.getConfig().setHostName(openerp_host);
					if(openerp_port != null)
						factory.getConfig().setPortNumber(Integer.parseInt(openerp_port));
					if(openerp_db != null)
						factory.getConfig().setDatabaseName(openerp_db);
					if(openerp_login != null)
						factory.getConfig().setUserName(openerp_login);
					if(openerp_password != null)
						factory.getConfig().setPassword(openerp_password);
  
					//Fix up filters for the main query on the main report
					//Skip subreports because it should join up with specific filters to the main report query
					if(parameter_ids != null &&  section instanceof MasterReport && factory.getQueryName().equals(selected_query_name)) {
						String model_path = "[" + factory.getConfig().getModelName() + "]";
						boolean has_filters = false;
						ArrayList<OpenERPFilterInfo> filters = factory.getConfig().getFilters();
						for(OpenERPFilterInfo filter : filters) {
							if (filter.getModelPath().equals(model_path)) {
								has_filters = true;
								break;
							}
						}

						if(has_filters == false)
							filters.add(new OpenERPFilterInfo(model_path, 1, "", "id", "in", parameter_ids));
						else
							parameters.put("ids", parameter_ids);
					}
				} else if(data_factory instanceof SQLReportDataFactory && (postgres_login != null || postgres_password != null || postgres_host != null || postgres_port != null || postgres_db != null)) {
					SQLReportDataFactory factory = (SQLReportDataFactory) data_factory;
					SQLReportDataFactory new_factory;
					DriverConnectionProvider new_settings;

					if(postgres_host == null || postgres_db == null)
						throw new Exception("Invalid JDBC data source settings passed: PostgreS server's hostname (or IP address) and the database name must be set if specifying custom connection settings.");

					if(postgres_login == null)
						postgres_login = factory.getUserField();

					if(postgres_password == null)
						postgres_password = factory.getPasswordField();

					if(postgres_port == null)
						postgres_port = "5432";

					String jdbc_url = "jdbc:postgresql://" + postgres_host + ":" + postgres_port + "/" + postgres_db;

					new_settings = new DriverConnectionProvider();
					new_settings.setDriver("org.postgresql.Driver");
					new_settings.setUrl(jdbc_url);
					new_settings.setProperty("user", postgres_login);
					new_settings.setProperty("password", postgres_password);
					new_settings.setProperty("::pentaho-reporting::name", "Custom PostgreS datasource");
					new_settings.setProperty("::pentaho-reporting::hostname", postgres_host);
					new_settings.setProperty("::pentaho-reporting::port", postgres_port);
					new_settings.setProperty("::pentaho-reporting::database-name", postgres_db);
					new_settings.setProperty("::pentaho-reporting::database-type", "POSTGRESQL");

					new_factory = new SQLReportDataFactory(new_settings);
					new_factory.setUserField(postgres_login);
					new_factory.setPasswordField(postgres_password);
					new_factory.setGlobalScriptLanguage(factory.getGlobalScriptLanguage());
					new_factory.setGlobalScript(factory.getGlobalScript());

					for(String one_query_name : factory.getQueryNames())
						new_factory.setQuery(one_query_name, factory.getQuery(one_query_name));

					factories.set(j, new_factory);
				}
			}
		}

		//Go through all children and fix up their datasources too
		for(int i = 0; i < section.getElementCount(); i++) {
			ReportElement e = section.getElement(i);

			if(e instanceof Section)
				fixConfiguration((Section) e);
		}
	}

	//Checks the validity of parameters values set earlier
	private void checkParameters(MasterReport report) throws Exception {
		DefaultParameterContext param_context = new DefaultParameterContext(report);
		ReportParameterDefinition param_def = report.getParameterDefinition();
		ReportParameterValidator validator = param_def.getValidator();
		ValidationResult validation_result = validator.validate(new ValidationResult(), param_def, param_context);

		for(int i = 0; i < param_def.getParameterCount(); i++) {
			for(ValidationMessage msg : validation_result.getErrors(param_def.getParameterDefinition(i).getName())) {
				logger.info("Parameter Error: " + msg.getMessage());
			}
		}
	}
}
