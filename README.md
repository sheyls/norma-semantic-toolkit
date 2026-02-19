
# BPMN to Rules

This software transforms a legal compliance processes represented using BPMN that follows a specific template into executable rules. 

## Requirements

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


1. You should be able to create BPMN compliance processes, using the [template](https://example.com). In order to edit the BPMN, you need to use [Camunda Modeler](https://camunda.com/platform/modeler/), which is free. 

2. 
