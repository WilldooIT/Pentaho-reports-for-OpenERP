import java.util.HashMap;
import java.util.Hashtable;
import java.util.ArrayList;
import java.util.Enumeration;
import java.io.ByteArrayOutputStream;

import org.apache.xmlrpc.server.XmlRpcServer;
import org.apache.xmlrpc.server.PropertyHandlerMapping;
import org.apache.xmlrpc.webserver.WebServer;
import org.apache.commons.codec.binary.Base64;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import org.pentaho.reporting.engine.classic.core.AbstractReportDefinition;
import org.pentaho.reporting.engine.classic.core.ClassicEngineBoot;
import org.pentaho.reporting.engine.classic.core.CompoundDataFactory;
import org.pentaho.reporting.engine.classic.core.Element;
import org.pentaho.reporting.engine.classic.core.MasterReport;
import org.pentaho.reporting.engine.classic.core.Section;

import org.pentaho.reporting.engine.classic.core.modules.output.table.csv.CSVReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.rtf.RTFReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.html.HtmlReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.table.xls.ExcelReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.pdf.PdfReportUtil;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.plaintext.PlainTextReportUtil;

import org.pentaho.reporting.engine.classic.core.util.ReportParameterValues;
import org.pentaho.reporting.engine.classic.extensions.datasources.openerp.OpenERPDataFactory;
import org.pentaho.reporting.libraries.fonts.LibFontBoot;
import org.pentaho.reporting.libraries.resourceloader.LibLoaderBoot;
import org.pentaho.reporting.libraries.resourceloader.Resource;
import org.pentaho.reporting.libraries.resourceloader.ResourceManager;

import com.debortoliwines.openerp.reporting.di.OpenERPFilterInfo;

public class KludgyReportServer {
	private static Log logger = LogFactory.getLog(KludgyReportServer.class);

	//One common manager instance to be initialised on startup
	private static ResourceManager manager;

	//Unique for every invocation
	private String openerp_host = null;
	private String openerp_port = null;
	private String openerp_db = null;
	private String openerp_login = null;
	private String openerp_password = null;
	private String output_type = "pdf";
	private Object parameter_ids = null;
	private HashMap<String, Object> parameters = new HashMap<String, Object>();
	private String encoded_prpt_file = null;

	public String execute(Hashtable args) throws Exception {
		try {
			for(Enumeration argnames = args.keys(); argnames.hasMoreElements();) {
				String argname = (String) argnames.nextElement();
				Object argval = args.get(argname); 
				logger.debug(argname + ": " + argval);
				if (argname.equals("_openerp_host"))
					openerp_host = (String) argval;
				else if (argname.equals("_openerp_port"))
					openerp_port = (String) argval;
				else if (argname.equals("_openerp_db"))
					openerp_db = (String) argval;
				else if (argname.equals("_openerp_login"))
					openerp_login = (String) argval;
				else if (argname.equals("_openerp_password"))
					openerp_password = (String) argval;
				else if (argname.equals("_prpt_file_content"))
					encoded_prpt_file = (String) argval;
				else if (argname.equals("_output_type"))
					output_type = (String) argval;
				else if (argname.equals("ids"))
					parameter_ids = argval;
				else parameters.put(argname, argval);
			}

			//Decode passed prpt file
			ByteArrayOutputStream temp_prpt_stream = new ByteArrayOutputStream();
			temp_prpt_stream.write(Base64.decodeBase64(encoded_prpt_file));

			//Load the report (we may be overriding Pentaho's caching mechanisms by doing this
			Resource res = manager.createDirectly(temp_prpt_stream.toByteArray(), MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();

			//Fix up data sources specified by parameters passed in
			fixConfiguration(report);

			//Pass through other parameters
			ReportParameterValues values = report.getParameterValues();
			for(String parameter_name : parameters.keySet()) {
				Object parameter_value = parameters.get(parameter_name);
				values.put(parameter_name, parameter_value);
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

			//Return the base64 encoded output
			String encoded_output_string = Base64.encodeBase64String(report_bin_out.toByteArray());
			logger.debug("Returning:\n" + encoded_output_string);
			return encoded_output_string;
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
				System.out.println(exception.getMessage());
				exception.printStackTrace();
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
			phm.addHandler("report", KludgyReportServer.class);
			rpc_server.setHandlerMapping(phm);

			server.start();
			logger.info("Started successfully");
			logger.info("Accepting requests");
		} catch(Exception exception) {
			logger.error(exception.getMessage());
			logger.error(ExceptionUtils.getStackTrace(exception));
		}
	}

	//DBW
	private void fixConfiguration(Section section) {
		//If one of the datasources is an OpenERP datasource, reset the connection to the passed parameters
		if(section instanceof AbstractReportDefinition) {
			String selected_query_name = ((AbstractReportDefinition) section).getQuery();

			CompoundDataFactory factories = (CompoundDataFactory) ((AbstractReportDefinition) section).getDataFactory();
			for(int j = 0; j < factories.size(); j++) {
				if (factories.getReference(j) instanceof OpenERPDataFactory) {
					OpenERPDataFactory factory = (OpenERPDataFactory) factories.getReference(j);

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
				}
			}
		}

		//Go through all children and fix up their datasources too
		for(int i = 0; i < section.getElementCount(); i++) {
			Element e = section.getElement(i);

			if(e instanceof Section)
				fixConfiguration((Section) e);
		}
	}
}
