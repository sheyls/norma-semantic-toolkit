
# BPMN to Rules

This software transforms a legal compliance processes represented using BPMN that follows a specific template into executable rules. 

## Requirements
- Camunda Modeler 8
- Python 3.8.10

## Set up

1. Set up Camunda Modeler
	1. Download and install [Camunda Modeler](https://camunda.com/platform/modeler/) version 8. It is [open source](https://github.com/camunda/camunda-modeler). 
	2. Install our template. Download [template](camunda-template/camunda8-compliance-template.json) and copy the `json` file to:

	Windows:
	`C:\Users\YOURUSER\AppData\Roaming\camunda-modeler\resources\element-templates`

Linux:
`/home/YOURUSER/.config/camunda-modeler/resources/element-templates`

macOS:
`/Users/YOURUSER/Library/Application Support/camunda-modeler/resources/element-templates`

If the folder `resources/element-templates` does not exists, feel free to create it. Once installed, restart Camunda Modeler and you should see be able to create a model, then create a task: you should see advanced the template in the Property Panel.


## How to run an example

1. Open a sample BPMN
Open the [example](examples/1.bpmn).
