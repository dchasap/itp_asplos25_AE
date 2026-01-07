import re

def unpack_template(config, simulations):

  if len(simulations) <= 0:
    return config, simulations

  sim = simulations[0]
  #print('Processing ' + sim)

  if '$' in sim:
    #print('Template found in ' + sim)

    if (config.has_section(sim)):
      #print('Expanding template ' + sim)
        
      template_variables = re.findall(r'\$\{([^}]+)\}', sim)
      if template_variables:
        variable = template_variables.pop()
        #print(variable)

        if (config.has_option(sim, variable)):
          values = config[sim][variable].split(' ')
          #print(values)

          expanded_simulations = []
          for value in values:     
            new_sim = sim.replace("${" + variable + "}", value)
            #print(new_sim)
            expanded_simulations.append(new_sim)
            # create a new section and copy options
            config.add_section(new_sim)

            for option in config.options(sim):

              if variable == option:
                config.set(new_sim, option, value)
              else:
                config.set(new_sim, option, config[sim][option])
              
          # remove old section
          config.remove_section(sim)
          # return new config and simulation list
          simulations.pop(0)
          for new_sim in expanded_simulations:
            #print(new_sim)
            #simulations.insert(0, new_sim)
            simulations.append(new_sim)

          #print("sims:" + str(simulations))
          config, unpacked_simulations = unpack_template(config, simulations)
          #config.set('EXPERIMENT', 'simulations', ' '.join(unpacked_simulations))
          return config, simulations 
            
        else:
          print('Option ' + variable + " not found!")
          exit(1)

      else:
        print('Could not find variable in template ' + sim)
        exit(1)
          
    else:
      print('Simulation ' + sim + ' not found!')
      exit(1)

      # remove template section
      config.remove_section(sim)
      # add expanded simulations to experiment
      config.set('EXPERIMENT', 'simulations', ' '.join(expanded_simulations))
  
  else: 
    simulations.pop(0)
    config, unpacked_simulations = unpack_template(config, simulations)
    unpacked_simulations.insert(0, sim)
    config.set('EXPERIMENT', 'simulations', ', '.join(unpacked_simulations))
    return config, simulations 


  return config, expanded_simulations
  


def preprocess(config, config_filename):
  
  print("Preprocessing configuration file...")

  simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

  unpack_template(config, simulations)

  # save the new generated config file
  filename = config_filename.split('/').pop()
  new_config_file = open('./exp_conf/autogen_conf/' + filename, 'w')
  config.write(new_config_file)
  
  return config