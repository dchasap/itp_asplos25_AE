import re

def _split_simulations(value):
  return [simulation.strip() for simulation in value.split(',') if simulation.strip()]


def _split_template_values(value):
  return [item for item in value.split(' ') if item]


def unpack_template(config, sim):

  if '$' not in sim:
    return config, [sim]

  if '$' in sim:
    if (config.has_section(sim)):
      template_variables = re.findall(r'\$\{([^}]+)\}', sim)
      if template_variables:
        variable = template_variables.pop()

        if (config.has_option(sim, variable)):
          values = _split_template_values(config[sim][variable])

          expanded_simulations = []
          for value in values:
            new_sim = sim.replace("${" + variable + "}", value)

            if not config.has_section(new_sim):
              config.add_section(new_sim)

            for option in config.options(sim):
              if variable == option:
                config.set(new_sim, option, value)
              else:
                config.set(new_sim, option, config[sim][option])

            config, unpacked_simulations = unpack_template(config, new_sim)
            expanded_simulations.extend(unpacked_simulations)

          config.remove_section(sim)
          return config, expanded_simulations
            
        else:
          print('Option ' + variable + " not found!")
          exit(1)

      else:
        print('Could not find variable in template ' + sim)
        exit(1)
          
    else:
      print('Simulation ' + sim + ' not found!')
      exit(1)

  return config, [sim]
  


def preprocess(config, config_filename):
  
  print("Preprocessing configuration file...")

  simulations = _split_simulations(config['EXPERIMENT']['simulations'])

  expanded_simulations = []
  for sim in simulations:
    config, unpacked_simulations = unpack_template(config, sim)
    expanded_simulations.extend(unpacked_simulations)

  config.set('EXPERIMENT', 'simulations', ', '.join(expanded_simulations))

  # save the new generated config file
  filename = config_filename.split('/').pop()
  new_config_file = open('./exp_conf/autogen_conf/' + filename, 'w')
  config.write(new_config_file)
  
  return config