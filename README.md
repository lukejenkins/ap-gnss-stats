# AP GNSS Stats

Tools for parsing and analyzing GNSS (Global Navigation Satellite System) statistics from Cisco Wi-Fi Access Points.

## To Do List

- [X] Handle "#show gnss info -> No GNSS detected"
- [X] Add parsing of "GNSS_PostProcessor"
- [X] Add parsing of "CiscoGNSS"
- [X] Add parsing of "Last Location Acquired"
- [X] Add support for parsing "show version"
- [X] Add support for parsing "show inventory"
- [X] Break out the parsing bits into a library
- [X] Add support dotenv for configuration
- [X] Add support for SSHing to APs and running the commands
  - [X] Add support for multiple SSH connections at once
- [X] Add CSV export functionality with comprehensive data flattening
- [X] ✅ **Bug Fix:** Resolved issue where APs marked successful lacked valid parsed data
- [ ] Add support for pushing the parsed data to Prometheus
- [ ] Add support for pushing the parsed data to InfluxDB
- [ ] Add example visualizations using Grafana
- [ ] Add support for accelerometer sensor data from APs
- [ ] Add support for pulling AP lists from Cisco DNA Center
- [ ] Add support for pulling AP lists from netbox

## AI Disclosure

**Here there be robots!** I *think* they are friendly, but they might just be very good at pretending. You might be a fool if you use this project for anything other than as an example of how silly it can be to use AI to code with.

> This project was developed with the assistance of language models from OpenAI and Anthropic, which provided suggestions and code snippets to enhance the functionality and efficiency of the tools. The models were used to generate code, documentation, distraction, moral support, moral turpitude, and explanations for various components of the project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
