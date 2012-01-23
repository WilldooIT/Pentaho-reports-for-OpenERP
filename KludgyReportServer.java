import org.apache.xmlrpc.server.XmlRpcServer;
import org.apache.xmlrpc.webserver.WebServer;
import org.apache.xmlrpc.*;
import org.apache.xmlrpc.server.PropertyHandlerMapping;
import org.apache.commons.codec.binary.Base64;

import java.text.NumberFormat;
import java.lang.Object;
import java.util.Date;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Hashtable;
import java.util.ResourceBundle;
import java.util.Hashtable;
import java.io.ByteArrayInputStream;
import java.io.*;
import java.sql.*;
import java.lang.Class;
import java.math.BigDecimal;
import java.io.InputStream;
import java.util.Locale;

import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.Enumeration;

import org.pentaho.reporting.engine.classic.core.AbstractReportDefinition;
import org.pentaho.reporting.engine.classic.core.ClassicEngineBoot;
import org.pentaho.reporting.engine.classic.core.CompoundDataFactory;
import org.pentaho.reporting.engine.classic.core.Element;
import org.pentaho.reporting.engine.classic.core.MasterReport;
import org.pentaho.reporting.engine.classic.core.Section;
import org.pentaho.reporting.engine.classic.core.modules.output.pageable.pdf.PdfReportUtil;
import org.pentaho.reporting.engine.classic.core.util.ReportParameterValues;
import org.pentaho.reporting.engine.classic.extensions.datasources.openerp.OpenERPDataFactory;
import org.pentaho.reporting.libraries.fonts.LibFontBoot;
import org.pentaho.reporting.libraries.resourceloader.LibLoaderBoot;
import org.pentaho.reporting.libraries.resourceloader.Resource;
import org.pentaho.reporting.libraries.resourceloader.ResourceManager;

import com.debortoliwines.openerp.reporting.di.OpenERPFilterInfo;


public class KludgyReportServer { 
	//One common manager instance to be initialised on startup
	private static ResourceManager manager;

	//Unique for every invocation
	private String openerp_host = null;
	private String openerp_port = null;
	private String openerp_db = null;
	private String openerp_login = null;
	private String openerp_password = null;
	private Object parameter_ids = null;
	private HashMap<String, Object> parameters = new HashMap<String, Object>();

	private String encoded_prpt_file = null;

	public String execute(Hashtable args) throws Exception {
		try {
			for(Enumeration argnames = args.keys(); argnames.hasMoreElements();) {
				String argname = (String) argnames.nextElement();
				Object argval = args.get(argname); 
				System.out.println(argname + ": " + argval);
				if (argname.equals("OEHost"))
					openerp_host = (String) argval;
				else if (argname.equals("OEPort"))
					openerp_port = (String) argval;
				else if (argname.equals("OEDB"))
					openerp_db = (String) argval;
				else if (argname.equals("OEUser"))
					openerp_login = (String) argval;
				else if (argname.equals("OEPass"))
					openerp_password = (String) argval;
				else if (argname.equals("PRPTFile"))
					encoded_prpt_file = (String) argval;
				else if (argname.equals("ids"))
					parameter_ids = argval;
				else parameters.put(argname, argval);
			}

			//Decode passed prpt file and write it out to a temp file
			File temp_prpt = File.createTempFile("tmp_prpt", Long.toString(System.nanoTime()));
			FileOutputStream temp_prpt_stream = new FileOutputStream(temp_prpt);
			temp_prpt_stream.write(Base64.decodeBase64(encoded_prpt_file));
			temp_prpt_stream.close();

			//Load the report from file and then delete the temporary file.
			Resource res = manager.createDirectly("file:" + temp_prpt.getAbsolutePath(), MasterReport.class);
			MasterReport report = (MasterReport) res.getResource();
			temp_prpt.delete();

			//Fix up data sources specified by parameters passed in
			fixConfiguration(report);

			//Pass through parameters
			ReportParameterValues values = report.getParameterValues();
			for(String parameter_name : parameters.keySet()) {
				Object parameter_value = parameters.get(parameter_name);
				values.put(parameter_name, parameter_value);
			}

			//Create the PDF
			File temp_pdf = File.createTempFile("tmp_pdf", Long.toString(System.nanoTime()));
			PdfReportUtil.createPDF(report, temp_pdf.getAbsolutePath());

			//Read in the contents of the generated PDF file and encode it to base64
			byte pdf_binary[] = new byte[(int) temp_pdf.length()];
			FileInputStream temp_pdf_stream = new FileInputStream(temp_pdf);
			temp_pdf_stream.read(pdf_binary);
			temp_pdf_stream.close();
			temp_pdf.delete();

			//Return the base64 encoded PDF
			String encoded_pdf_string = Base64.encodeBase64String(pdf_binary);
			System.out.println("Returning:\n" + encoded_pdf_string);
			return encoded_pdf_string;
		} catch(Exception exception) {
			System.out.println(exception.getMessage());
			exception.printStackTrace();
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

			java.net.InetAddress server_spec = java.net.Inet4Address.getByName("localhost");

			System.out.println("KludgyReportServer: Attempting to start XML-RPC Server at " + server_spec.toString() + ":" + port + "...");
			WebServer server = new WebServer(port, server_spec);
			XmlRpcServer rpc_server = server.getXmlRpcServer();

			PropertyHandlerMapping phm = new PropertyHandlerMapping();
			phm.addHandler("report", KludgyReportServer.class);
			rpc_server.setHandlerMapping(phm);

			server.start();
			System.out.println("KludgyReportServer: Started successfully.");
			System.out.println("KludgyReportServer: Accepting requests (halt program to stop.)");
		} catch(Exception exception) {
			System.err.println("KludgyReportServer: " + exception);
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
