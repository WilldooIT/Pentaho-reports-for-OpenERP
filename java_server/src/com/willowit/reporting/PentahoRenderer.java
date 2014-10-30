package com.willowit.reporting;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Hashtable;

import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.pentaho.reporting.engine.classic.core.AbstractReportDefinition;
import org.pentaho.reporting.engine.classic.core.ClassicEngineBoot;
import org.pentaho.reporting.engine.classic.core.CompoundDataFactory;
import org.pentaho.reporting.engine.classic.core.DataFactory;
import org.pentaho.reporting.engine.classic.core.MasterReport;
import org.pentaho.reporting.engine.classic.core.ReportElement;
import org.pentaho.reporting.engine.classic.core.RootLevelBand;
import org.pentaho.reporting.engine.classic.core.Section;
import org.pentaho.reporting.engine.classic.core.SubReport;
import org.pentaho.reporting.engine.classic.core.modules.misc.datafactory.sql.DriverConnectionProvider;
import org.pentaho.reporting.engine.classic.core.modules.misc.datafactory.sql.SQLReportDataFactory;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.pdf.PdfReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.plaintext.PlainTextReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.csv.CSVReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.html.HtmlReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.rtf.RTFReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.xls.ExcelReportUtil;
import org.pentaho.reporting.engine.classic.core.parameters.DefaultParameterContext;
import org.pentaho.reporting.engine.classic.core.parameters.ListParameter;
import org.pentaho.reporting.engine.classic.core.parameters.ParameterAttributeNames;
import org.pentaho.reporting.engine.classic.core.parameters.ParameterDefinitionEntry;
import org.pentaho.reporting.engine.classic.core.parameters.ParameterValues;
import org.pentaho.reporting.engine.classic.core.parameters.ReportParameterDefinition;
import org.pentaho.reporting.engine.classic.core.parameters.ReportParameterValidator;
import org.pentaho.reporting.engine.classic.core.parameters.ValidationMessage;
import org.pentaho.reporting.engine.classic.core.parameters.ValidationResult;
import org.pentaho.reporting.engine.classic.core.util.ReportParameterValues;
import org.pentaho.reporting.engine.classic.extensions.datasources.openerp.OpenERPDataFactory;
import org.pentaho.reporting.libraries.fonts.LibFontBoot;
import org.pentaho.reporting.libraries.resourceloader.LibLoaderBoot;
import org.pentaho.reporting.libraries.resourceloader.Resource;
import org.pentaho.reporting.libraries.resourceloader.ResourceManager;

import com.debortoliwines.openerp.reporting.di.OpenERPFilterInfo;

public class PentahoRenderer {
	private static Log logger = LogFactory.getLog(PentahoRenderer.class);

	//One common manager instance to be initialised on startup
	private static ResourceManager manager;

	//Common method
	public static Exception bootPentaho() {
		Exception exception = null;
		if(ClassicEngineBoot.getInstance().isBootDone() == false) {
			LibLoaderBoot.getInstance().start();
			LibFontBoot.getInstance().start();
			ClassicEngineBoot.getInstance().start();

			exception = ClassicEngineBoot.getInstance().getBootFailureReason();
		}

		return exception;
	}

	public PentahoRenderer() {
		if(manager == null) {
			manager = new ResourceManager();
			manager.registerDefaults();
		}
	}

	//Internal functions
	//DBW
	private void fixOpenERPDataFactoryConfiguration(OpenERPDataFactory factory, HashMap<String, String> openerp_settings, HashMap<String, ?> parameters, Section section) {
		String selected_query_name = ((AbstractReportDefinition) section).getQuery();

		//Fix up connection parameters
		if(openerp_settings != null) {
			String openerp_host = openerp_settings.get("host");
			String openerp_port = openerp_settings.get("port");
			String openerp_db = openerp_settings.get("db");
			String openerp_login = openerp_settings.get("login");
			String openerp_password = openerp_settings.get("password");

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
		}

		//Fix up filters for the main query on the main report
		//Skip subreports because it should join up with specific filters to the main report query
		if(parameters != null && parameters.get("ids") != null && section instanceof MasterReport && factory.getQueryName().equals(selected_query_name)) {
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
				filters.add(new OpenERPFilterInfo(model_path, 1, "", "id", "in", parameters.get("ids")));
		}
	}

	private SQLReportDataFactory fixSQLDataFactoryConfiguration(SQLReportDataFactory factory, HashMap<String, String> postgres_settings) throws Exception {
		SQLReportDataFactory new_factory;
		DriverConnectionProvider new_settings;

		String postgres_host = postgres_settings.get("host");
		String postgres_port = postgres_settings.get("port");
		String postgres_db = postgres_settings.get("db");
		String postgres_login = postgres_settings.get("login");
		String postgres_password = postgres_settings.get("password");

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

		//The following may not be necessary since we set the JDBC URL
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
			new_factory.setQuery(one_query_name, factory.getQuery(one_query_name), factory.getScriptingLanguage(one_query_name), factory.getScript(one_query_name));

		return new_factory;
	}

	private void fixConfiguration(Section section, HashMap<String, String> openerp_settings, HashMap<String, String> postgres_settings, HashMap<String, ?> parameters) throws Exception {
		//If one of the datasources is an OpenERP datasource, reset the connection to the passed parameters
		if(section instanceof AbstractReportDefinition) {

			CompoundDataFactory factories = (CompoundDataFactory) ((AbstractReportDefinition) section).getDataFactory();
			for(int j = 0; j < factories.size(); j++) {
				DataFactory data_factory = factories.getReference(j);
				if(data_factory instanceof OpenERPDataFactory)
					fixOpenERPDataFactoryConfiguration((OpenERPDataFactory) data_factory, openerp_settings, parameters, section);
				else if(data_factory instanceof SQLReportDataFactory && postgres_settings != null) {
					String[] postgres_setting_names = {"host", "port", "db", "login", "password"};

					boolean custom_settings = false;
					for(String custom_setting_name : postgres_setting_names)
						custom_settings |= (postgres_settings.get(custom_setting_name) != null);

					if(custom_settings)
						factories.set(j, fixSQLDataFactoryConfiguration((SQLReportDataFactory) data_factory, postgres_settings));
				}
			}
		}

		//Go through all children and fix up their datasources too
		for(int i = 0; i < section.getElementCount(); i++) {
			ReportElement e = section.getElement(i);

			if(e instanceof Section)
				fixConfiguration((Section) e, openerp_settings, postgres_settings, parameters);
			
			// Fix subreports
			if (e instanceof RootLevelBand){
				for (SubReport sub : ((RootLevelBand) e).getSubReports())  
					fixConfiguration((Section) sub, openerp_settings, postgres_settings, parameters);
			}
		}
	}

	//Checks the validity of parameters values set earlier
	//Not used at the moment
	private void checkParameters(MasterReport report) throws Exception {
		DefaultParameterContext param_context = new DefaultParameterContext(report);
		ReportParameterDefinition param_def = report.getParameterDefinition();
		ReportParameterValidator validator = param_def.getValidator();
		ValidationResult validation_result = validator.validate(new ValidationResult(), param_def, param_context);

		for(int i = 0; i < param_def.getParameterCount(); i++)
			for(ValidationMessage msg : validation_result.getErrors(param_def.getParameterDefinition(i).getName()))
				logger.info("Parameter Error: " + msg.getMessage());
	}

	//Helper functions
	private HashMap<String, Object> getParametersTypes(MasterReport report) throws Exception {
		ReportParameterDefinition param_def = report.getParameterDefinition();
		ParameterDefinitionEntry[] param_def_entries = param_def.getParameterDefinitions();

		HashMap<String, Object> name_to_type = new HashMap<String, Object>();

		for(ParameterDefinitionEntry param_def_entry : param_def_entries)
			name_to_type.put(param_def_entry.getName(), param_def_entry.getValueType());

		return name_to_type;
	}

	private void typeCastAndStore(ReportParameterValues target, String parameter_type, String parameter_name, Object parameter_value) {
		if(parameter_type.equals("java.lang.Long"))
			target.put(parameter_name, new Long(((Integer) parameter_value)));
		else if(parameter_type.equals("java.lang.Short"))
			target.put(parameter_name, ((Integer) parameter_value).shortValue());
		else if(parameter_type.equals("java.math.BigInteger"))
			target.put(parameter_name, java.math.BigInteger.valueOf(((Integer) parameter_value)));
		else if(parameter_type.equals("java.lang.Float"))
			target.put(parameter_name, ((Double) parameter_value).floatValue());
		else if(parameter_type.equals("java.math.BigDecimal"))
			target.put(parameter_name, java.math.BigDecimal.valueOf(((Double) parameter_value)));
		else if(parameter_type.equals("java.sql.Date"))
			target.put(parameter_name, new java.sql.Date(((java.util.Date) parameter_value).getTime()));
		else if(parameter_type.equals("java.sql.Time"))
			target.put(parameter_name, new java.sql.Time(((java.util.Date) parameter_value).getTime()));
		else if(parameter_type.equals("java.sql.Timestamp"))
			target.put(parameter_name, new java.sql.Timestamp(((java.util.Date) parameter_value).getTime()));
		else
			target.put(parameter_name, parameter_value);
	}

	private byte[] renderReport(MasterReport report, String output_type) throws Exception {
		//Create the report output stream
		ByteArrayOutputStream report_bin_out = new ByteArrayOutputStream();

		if(output_type.equals("pdf"))
			PdfReportUtil.createPDF(report, report_bin_out);
		else if(output_type.equals("xls"))
			ExcelReportUtil.createXLS(report, report_bin_out);
		else if(output_type.equals("xlsx"))
			ExcelReportUtil.createXLSX(report, report_bin_out);
		else if(output_type.equals("csv"))
			CSVReportUtil.createCSV(report, report_bin_out, null);
		else if(output_type.equals("rtf"))
			RTFReportUtil.createRTF(report, report_bin_out);
		else if(output_type.equals("html"))
			HtmlReportUtil.createStreamHTML(report, report_bin_out);
		else if(output_type.equals("txt"))
			PlainTextReportUtil.createPlainText(report, report_bin_out);

		return report_bin_out.toByteArray();
	}

	//Exported methods
	@SuppressWarnings("unchecked")
  public ArrayList<HashMap<String, ?>> getParameterInfo(Hashtable<String, ?> args) throws Exception {
		ArrayList<HashMap<String, ?>> ret_val = new ArrayList<HashMap<String, ?>>();

		//FIXME: redundant code
		HashMap<String, Object> parameters = new HashMap<String, Object>();
		HashMap<String, HashMap<String, ?>> connection_settings = new HashMap<String, HashMap<String, ?>>();
		HashMap<String, String> openerp_settings = new HashMap<String, String>();
		HashMap<String, String> postgres_settings = new HashMap<String, String>();

		try {
			byte[] prpt_file_content = (byte[]) args.get("prpt_file_content");

			if(prpt_file_content == null)
				throw new Exception("No report content sent!");		

			//FIXME: redundant code
			connection_settings = (HashMap<String, HashMap<String, ?>>) args.get("connection_settings");
			parameters = (HashMap<String, Object>) args.get("report_parameters");
			openerp_settings = (HashMap<String, String>) connection_settings.get("openerp");
			postgres_settings = (HashMap<String, String>) connection_settings.get("postgres");

			Resource res = manager.createDirectly(prpt_file_content, MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();

			fixConfiguration(report, openerp_settings, postgres_settings, parameters);
			
			if (parameters != null){
			  HashMap<String, Object> parameters_types = getParametersTypes(report);
			  // Set parameters available
			  ReportParameterValues values = report.getParameterValues();
			  for(String parameter_name : parameters.keySet()) {
			    Object parameter_value = parameters.get(parameter_name);
  
			    if(parameters_types.get(parameter_name) != null){
			      typeCastAndStore(values, ((Class<?>) parameters_types.get(parameter_name)).getName(), parameter_name, parameter_value);
			    }
			  }
			}

			//New stuff
			ReportParameterDefinition param_def = report.getParameterDefinition();
			ParameterDefinitionEntry[] param_def_entries = param_def.getParameterDefinitions();
			DefaultParameterContext param_context = new DefaultParameterContext(report);
			for(ParameterDefinitionEntry param_def_entry : param_def_entries) {
				HashMap<String, Object> one_param_info = new HashMap<String, Object>();
				HashMap<String, Object> core_namespace_attributes = new HashMap<String, Object>();

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
				one_param_info.put("attributes", core_namespace_attributes);

				String[] param_attr_names = param_def_entry.getParameterAttributeNames(ParameterAttributeNames.Core.NAMESPACE);
				for(String param_attr_name : param_attr_names) {
					String param_attr = param_def_entry.getParameterAttribute(ParameterAttributeNames.Core.NAMESPACE, param_attr_name, param_context);
					core_namespace_attributes.put(param_attr_name, param_attr);
					logger.debug("Attribute: " + param_attr_name + " = " + param_attr);
				}

				if(param_def_entry instanceof ListParameter) {
					ParameterValues param_vals = ((ListParameter) param_def_entry).getValues(param_context);
					int num_options = param_vals.getRowCount();
					ArrayList<ArrayList<Object>> selection_options = new ArrayList<ArrayList<Object>>(num_options);

					for(int i = 0; i < num_options; i++) {
						ArrayList<Object> one_option = new ArrayList<Object>();

						one_option.add(param_vals.getKeyValue(i));
						one_option.add(param_vals.getTextValue(i));

						selection_options.add(one_option);
						logger.debug("Selection option: {" + param_vals.getKeyValue(i) + ": " + param_vals.getTextValue(i) + "}");
					}

					one_param_info.put("selection_options", selection_options);
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

	@SuppressWarnings("unchecked")
  public byte[] execute(Hashtable<String, ?> args) throws Exception {
		byte[] prpt_file_content = null;
		String output_type = null;

		HashMap<String, Object> parameters = new HashMap<String, Object>();
		HashMap<String, HashMap<String, ?>> connection_settings = new HashMap<String, HashMap<String, ?>>();
		HashMap<String, String> openerp_settings = new HashMap<String, String>();
		HashMap<String, String> postgres_settings = new HashMap<String, String>();

		logger.debug(args);

		try {
			prpt_file_content = (byte[]) args.get("prpt_file_content");
			output_type = (String) args.get("output_type");

			if(prpt_file_content == null)
				throw new Exception("No report content sent!");		

			if(output_type == null)
				output_type = "pdf";

			connection_settings = (HashMap<String, HashMap<String, ?>>) args.get("connection_settings");
			parameters = (HashMap<String, Object>) args.get("report_parameters");
			openerp_settings = (HashMap<String, String>) connection_settings.get("openerp");
			postgres_settings = (HashMap<String, String>) connection_settings.get("postgres");

			//Load the report (we may be overriding Pentaho's caching mechanisms by doing this
			Resource res = manager.createDirectly(prpt_file_content, MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();
			HashMap<String, Object> parameters_types = getParametersTypes(report);

			//Fix up data sources specified by parameters passed in
			fixConfiguration(report, openerp_settings, postgres_settings, parameters);

			//Pass through other parameters
			ReportParameterValues values = report.getParameterValues();
			for(String parameter_name : parameters.keySet()) {
				Object parameter_value = parameters.get(parameter_name);

				if(parameters_types.get(parameter_name) != null)
					typeCastAndStore(values, ((Class<?>) parameters_types.get(parameter_name)).getName(), parameter_name, parameter_value);
			}

			return renderReport(report, output_type);
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));

			throw exception;
		}
	}
}
